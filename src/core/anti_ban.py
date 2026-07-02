"""Camada de blindagem anti-ban contra o WAF do Cloudflare.

Fundamento: um bloqueio 1020/1015 do Cloudflare dispara por dois motivos
mensuráveis — (1) taxa de requisições acima de um limiar dentro de uma janela
de tempo e (2) insistência depois que o servidor já sinalizou bloqueio. Este
módulo ataca os dois:

* ``RateGovernor`` — um *token bucket* que limita a taxa média e a rajada de
  navegações a um ritmo humano. Bloqueia (dorme) até haver "orçamento" para a
  próxima ação pesada (navegar/recarregar).
* ``CircuitBreaker`` — ao primeiro sinal de bloqueio real (1020) ou após N
  falhas consecutivas, "abre o circuito": entra em cooldown com *backoff
  exponencial* e persiste o estado em disco, para que reiniciar o processo não
  volte a martelar um IP já banido.
* ``classify_block`` / ``assess_page`` — distinguem um desafio de JS (passável
  com navegador) de um bloqueio de firewall 1020 (só resolve com tempo ou troca
  de IP). Sem essa distinção o pipeline reabre o navegador à toa e aprofunda o
  ban.

Nada aqui garante imunidade absoluta — o veredito final é sempre do servidor.
O objetivo é manter o comportamento dentro de uma faixa defensável e parar de
imediato quando o bloqueio acontece.
"""

import os
import json
import time
import random
import logging
import threading

logger = logging.getLogger(__name__)


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except (ValueError, TypeError):
        return float(default)


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (ValueError, TypeError):
        return int(default)


class BlockedError(Exception):
    """Levantada quando o Cloudflare bloqueia o IP (1020/1015) — não adianta
    reabrir o navegador; o circuito já foi aberto pelo chamador."""


class BlockType:
    OK = "OK"
    CHALLENGE = "CHALLENGE"  # "Just a moment" — passável com navegador real
    BLOCKED = "BLOCKED"  # 1020 "you have been blocked" — IP flagrado
    RATE_LIMITED = "RATE_LIMITED"  # 1015 / HTTP 429 / "atividade incomum"
    MAINTENANCE = "MAINTENANCE"  # /manutencao/ , block.php


# Ordem importa: marcadores mais específicos/graves primeiro.
def classify_block(text="", title="", status=None, url=""):
    """Classifica a resposta atual do site a partir do corpo, título, status
    HTTP e URL. Conservador: um 403 genérico do Cloudflare sem sinais de
    desafio é tratado como BLOCKED (melhor parar do que insistir)."""
    t = (text or "").lower()
    ti = (title or "").lower()
    u = (url or "").lower()

    if "/manutencao/" in u or "block.php" in u:
        return BlockType.MAINTENANCE

    if (
        status == 429
        or "error 1015" in t
        or "rate limited" in t
        or "you are being rate limited" in t
        or "atividade incomum" in t
    ):
        return BlockType.RATE_LIMITED

    if (
        "you have been blocked" in t
        or "sorry, you have been" in t
        or "error 1020" in t
        or "access denied" in t
    ):
        return BlockType.BLOCKED

    if (
        "just a moment" in t
        or "just a moment" in ti
        or "challenge-platform" in t
        or "cf-challenge" in t
        or "checking your browser" in t
        or "verificando se você é humano" in t
        or "attention" in ti
        or "moment" in ti
    ):
        return BlockType.CHALLENGE

    # Fallback conservador: página curta do Cloudflare com 403 e sem marca de
    # desafio provavelmente é um 1020.
    if status == 403 and "cloudflare" in t and len(t) < 8000:
        return BlockType.BLOCKED

    return BlockType.OK


def assess_page(page):
    """Lê título + corpo (defensivamente, limitado) de uma página Playwright e
    retorna o BlockType. Nunca levanta exceção — em erro retorna OK."""
    try:
        title = page.title() or ""
    except Exception:
        title = ""
    try:
        text = page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 4000) : ''"
        )
    except Exception:
        text = ""
    try:
        url = page.url or ""
    except Exception:
        url = ""
    return classify_block(text=text, title=title, url=url)


class RateGovernor:
    """Token bucket. Cada ação pesada custa 1 token; os tokens reabastecem a
    ``1/refill_seconds`` por segundo até ``capacity``. Garante ainda um
    intervalo mínimo (``min_gap``) entre ações. Isso limita a rajada a
    ``capacity`` e a taxa média a ``1/refill_seconds`` navegações por segundo —
    o que mantém o tráfego num ritmo humano e abaixo do limiar do WAF."""

    def __init__(
        self,
        capacity=None,
        refill_seconds=None,
        min_gap=None,
        time_fn=time.monotonic,
        sleep_fn=time.sleep,
    ):
        self.capacity = (
            capacity if capacity is not None else _env_float("AB_BUCKET_CAPACITY", 3)
        )
        self.refill_seconds = (
            refill_seconds
            if refill_seconds is not None
            else _env_float("AB_REFILL_SECONDS", 20)
        )
        self.min_gap = min_gap if min_gap is not None else _env_float("AB_MIN_GAP", 8)
        self._time = time_fn
        self._sleep = sleep_fn
        self._tokens = self.capacity
        self._last_refill = self._time()
        self._last_action = None
        self._lock = threading.Lock()

    def _refill(self):
        now = self._time()
        elapsed = now - self._last_refill
        if elapsed > 0 and self.refill_seconds > 0:
            self._tokens = min(
                self.capacity, self._tokens + elapsed / self.refill_seconds
            )
            self._last_refill = now

    def _compute_wait(self):
        """Retorna quantos segundos é preciso esperar agora (sem dormir).
        Isolado para ser testável de forma determinística."""
        self._refill()
        now = self._time()
        gap_wait = 0.0
        if self._last_action is not None:
            gap_wait = self.min_gap - (now - self._last_action)
        token_wait = 0.0
        if self._tokens < 1:
            token_wait = (1 - self._tokens) * self.refill_seconds
        return max(gap_wait, token_wait, 0.0)

    def wait_turn(self, label="ação"):
        """Bloqueia até ser seguro executar a próxima ação pesada e então
        consome 1 token."""
        with self._lock:
            while True:
                wait = self._compute_wait()
                if wait <= 0:
                    break
                wait += random.uniform(0, min(3.0, wait * 0.25))  # jitter
                logger.info(
                    f"[ANTI-BAN] Aguardando {wait:.1f}s antes de '{label}' (ritmo humano)..."
                )
                self._sleep(wait)
            self._tokens -= 1
            self._last_action = self._time()


class CircuitBreaker:
    """Disjuntor com backoff exponencial e estado persistido em disco.

    Estados: fechado (opera), aberto (em cooldown, recusa trabalho). Ao abrir,
    o cooldown dobra a cada disparo consecutivo até ``max_cooldown`` e é gravado
    em ``state_path`` — assim, reiniciar o processo respeita o tempo restante em
    vez de voltar a bater no IP banido."""

    def __init__(self, state_path=None, time_fn=time.time):
        data_dir = os.environ.get("DATA_DIR", "data")
        self.state_path = state_path or os.path.join(data_dir, "anti_ban_state.json")
        self.fail_threshold = _env_int("AB_FAIL_THRESHOLD", 3)
        self.base_cooldown = _env_float("AB_BLOCK_COOLDOWN", 1200)  # 20 min
        self.max_cooldown = _env_float("AB_MAX_COOLDOWN", 7200)  # 2 h
        self._time = time_fn
        self._consec_fails = 0
        self._open_until = 0.0
        self._trip_count = 0
        self._last_trip = 0.0
        self._load()

    def _load(self):
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._open_until = float(data.get("open_until", 0.0))
            self._trip_count = int(data.get("trip_count", 0))
            self._last_trip = float(data.get("last_trip", 0.0))
            # Decai o histórico de disparos se já faz muito tempo do último,
            # para os cooldowns não escalarem para sempre.
            if self._last_trip and (self._time() - self._last_trip) > (
                self.max_cooldown * 2
            ):
                self._trip_count = 0
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            pass
        except Exception as e:
            logger.debug(f"[ANTI-BAN] Falha ao ler estado do breaker: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "open_until": self._open_until,
                        "trip_count": self._trip_count,
                        "last_trip": self._last_trip,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.debug(f"[ANTI-BAN] Falha ao gravar estado do breaker: {e}")

    def remaining(self):
        return max(0.0, self._open_until - self._time())

    def is_open(self):
        return self.remaining() > 0

    def trip(self, reason=""):
        """Abre o circuito com cooldown escalonado. Retorna o cooldown (s)."""
        self._trip_count += 1
        factor = 2 ** (self._trip_count - 1)
        cooldown = min(self.max_cooldown, self.base_cooldown * factor)
        self._last_trip = self._time()
        self._open_until = self._last_trip + cooldown
        self._consec_fails = 0
        self._save()
        logger.error(
            f"[ANTI-BAN] 🔴 CIRCUITO ABERTO ({reason}). Pausa obrigatória de "
            f"{cooldown / 60:.0f} min. Troque de IP (hotspot) ou aguarde."
        )
        return cooldown

    def record_failure(self, reason=""):
        """Registra uma falha 'mole' (capítulo incompleto). Ao acumular
        ``fail_threshold`` consecutivas, dispara o circuito. Retorna True se
        disparou."""
        self._consec_fails += 1
        logger.warning(
            f"[ANTI-BAN] Falha {self._consec_fails}/{self.fail_threshold} "
            f"consecutiva{(' — ' + reason) if reason else ''}."
        )
        if self._consec_fails >= self.fail_threshold:
            self.trip(f"{self._consec_fails} falhas consecutivas")
            return True
        return False

    def record_success(self):
        """Zera o contador de falhas e alivia o histórico de disparos."""
        changed = self._consec_fails or self._trip_count
        self._consec_fails = 0
        if self._trip_count:
            self._trip_count = max(0, self._trip_count - 1)
        if changed:
            self._save()


def human_pause(label="pausa", lo=None, hi=None, sleep_fn=time.sleep):
    """Dorme um intervalo aleatório humano (padrão: pausa entre capítulos)."""
    lo = lo if lo is not None else _env_float("AB_CHAPTER_PAUSE_MIN", 20)
    hi = hi if hi is not None else _env_float("AB_CHAPTER_PAUSE_MAX", 45)
    if hi < lo:
        hi = lo
    secs = random.uniform(lo, hi)
    logger.info(f"[ANTI-BAN] Pausa de {secs:.0f}s ({label}).")
    sleep_fn(secs)
    return secs


# --- Singletons de processo -------------------------------------------------
_governor = None
_breaker = None
_singleton_lock = threading.Lock()


def get_governor():
    global _governor
    if _governor is None:
        with _singleton_lock:
            if _governor is None:
                _governor = RateGovernor()
    return _governor


def get_breaker():
    global _breaker
    if _breaker is None:
        with _singleton_lock:
            if _breaker is None:
                _breaker = CircuitBreaker()
    return _breaker


def reset_singletons():
    """Apenas para testes: descarta as instâncias globais."""
    global _governor, _breaker
    with _singleton_lock:
        _governor = None
        _breaker = None
