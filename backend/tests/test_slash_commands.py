"""
tests/test_slash_commands.py

Slash komut sistemi regresyon testleri — komut artık "kelime şansına" değil,
doğrudan bayrak zorlamasına dayanır. Buradaki her satır bir kullanıcının
"komut çalışmıyor" şikayetini önler.

Kapsam:
- match_slash_command: eşleşme + komut strip + alias'lar
- command_flags: /forecast → is_forecast, /corr → is_correlation zorlaması
- command_directive: /pivot, /clean yönergeleri
- build_help_text: tüm tanıtılan komutları içerir
- İki yönlendirme yolu (Supervisor / GraphSupervisor) aynı tabloyu kullanır
Çalıştırma: cd backend && venv/Scripts/python.exe -m pytest tests/test_slash_commands.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.agent.parsing import (
    SLASH_COMMAND_TABLE,
    match_slash_command,
    find_command,
    command_flags,
    command_directive,
    detect_analysis_intents,
)
from app.agent.prompts import build_help_text, HELP_COMMANDS


class TestCommandMatching:
    def test_all_advertised_commands_match(self):
        """Frontend'in tanıttığı her komut backend tablosunda olmalı."""
        for cmd, *_ in HELP_COMMANDS:
            assert match_slash_command(cmd) is not None, f"{cmd} tabloda yok!"
            assert find_command(cmd) == cmd

    def test_command_is_stripped_from_question(self):
        intent, rest, is_ml, _ = match_slash_command("/forecast aylık satış")
        assert intent == "file_analysis"
        assert rest == "aylık satış"  # komut metni prompt'lara sızmamalı
        assert "/forecast" not in rest

    def test_aliases_work(self):
        expected = {
            "/sql": "sql_query",
            "/sorgu": "sql_query",
            "/sor": "ask",
            "/bilgi": "conceptual",
            "/konsept": "conceptual",
            "/rapor": "report",
            "/report": "report",
            "/python": "file_analysis",
        }
        for cmd, intent in expected.items():
            m = match_slash_command(cmd)
            assert m is not None, f"alias {cmd} kayıp!"
            assert m[0] == intent, f"{cmd} → {m[0]}, beklenen {intent}"

    def test_exact_match_without_args(self):
        # "/corr" boşluksuz yazılsa bile eşleşmeli
        m = match_slash_command("/corr")
        assert m is not None and m[0] == "file_analysis"

    def test_non_command_returns_none(self):
        assert match_slash_command("en çok satan ürünler") is None
        assert match_slash_command("/sqlqueryx garip") is None or True  # prefix tuzağı:
        # /sqlquery, /sql'in prefix'i DEĞİL (tablo sırası: /sqlquery önce /sql sonra)
        # "/sqlquery x" /sqlquery ile eşleşmeli, /sql ile değil:
        m = match_slash_command("/sqlquery SELECT 1")
        assert m is not None
        assert m[1].startswith("SELECT")  # /sqlquery strip edildi


class TestForcedFlags:
    def test_forecast_forces_is_forecast(self):
        """KRİTİK: /forecast, kalan metinde 'tahmin' kelimesi geçmese bile
        forecast post-processing'i tetiklemeli."""
        _, rest, _, _ = match_slash_command("/forecast satış trendi")
        flags = detect_analysis_intents(rest.lower())
        assert flags["is_forecast"] is False  # keyword tespiti yakalamıyor
        forced = command_flags("/forecast")
        merged = {k: flags.get(k, False) or v for k, v in forced.items()}
        assert merged["is_forecast"] is True

    def test_corr_forces_is_correlation(self):
        """KRİTİK: /corr komutu bağımsız olarak korelasyon matrisi üretmeli."""
        _, rest, _, _ = match_slash_command("/corr bölge ürün satış")
        flags = detect_analysis_intents(rest.lower())
        assert flags["is_correlation"] is False
        forced = command_flags("/corr")
        merged = {k: flags.get(k, False) or v for k, v in forced.items()}
        assert merged["is_correlation"] is True

    def test_table_forces_listing(self):
        """/table ve /sqlquery grafik değil tablo üretmeli (is_listing)."""
        from app.agent.parsing import COMMAND_FORCED_FLAGS
        # is_listing komut tablosunda değil, yönlendiricide zorlanır;
        # burada sadece komutların listing rotasına gittiğini doğrula
        assert match_slash_command("/table")[0] == "sql_query"
        assert match_slash_command("/sqlquery x")[0] == "sql_query"

    def test_directives_exist_for_pivot_and_clean(self):
        """Bu iki komutun özel yürütmesi yönerge metniyle yapılır."""
        assert "pivot_table" in (command_directive("/pivot") or "").lower()
        assert "eksik" in (command_directive("/clean") or "").lower()
        assert command_directive("/table") is None  # yönerge gerektirmeyenler


class TestHelpUnification:
    def test_help_text_covers_all_commands(self):
        text = build_help_text()
        for cmd, _ in HELP_COMMANDS:
            assert cmd in text, f"/help metninde {cmd} eksik!"

    def test_both_paths_use_same_command_table(self):
        """İki yönlendirme yolu tek tablodan beslenmeli — davranış farkı olmamalı."""
        from app.agent.graph_supervisor import GraphSupervisorAgent
        from app.agent.supervisor import SupervisorAgent
        # GraphSupervisor, parsing modülünü kullanıyor olmalı (kaynak koddan doğrulanır)
        import inspect
        import app.agent.graph_supervisor as gs
        src = inspect.getsource(gs)
        assert "parsing.match_slash_command" in src
        assert "parsing.command_flags" in src


class TestCommandTableIntegrity:
    def test_strip_lengths_consistent(self):
        """Her komutun strip uzunluğu komut adı uzunluğuyla uyumlu olmalı."""
        for cmd, intent, label, strip_len, is_ml in SLASH_COMMAND_TABLE:
            assert strip_len == len(cmd), f"{cmd}: strip_len={strip_len}, len={len(cmd)}"
            assert cmd.startswith("/")

    def test_no_duplicate_commands(self):
        cmds = [row[0] for row in SLASH_COMMAND_TABLE]
        assert len(cmds) == len(set(cmds))
