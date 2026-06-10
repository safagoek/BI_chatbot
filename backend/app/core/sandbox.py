import os
import sys
import json
import tempfile
import subprocess
from typing import Dict, Any, List, Optional

class SandboxExecutionError(Exception):
    pass

class PythonSandbox:
    def __init__(self, timeout_seconds: float = 10.0, max_memory_mb: int = 512):
        self.timeout_seconds = timeout_seconds
        self.max_memory_mb = max_memory_mb

    def _check_code_safety(self, code: str) -> Optional[str]:
        """
        Validates that the user/LLM generated code does not contain malicious system calls or imports.
        """
        import ast

        forbidden_builtins = {
            "eval", "exec", "open", "__import__", "getattr", "setattr", "locals", "globals",
            "dir", "vars", "compile", "breakpoint", "input", "help", "execfile", "evalfile"
        }

        forbidden_modules = {
            "os", "sys", "subprocess", "shutil", "socket", "urllib", "requests", "pty", "ctypes", 
            "importlib", "platform", "pickle", "marshal", "shelve", "dbm", "sqlite3", "tempfile"
        }

        unsafe_keywords = [
            "__builtins__", "subprocess", "os.system", "os.popen", "shutil", 
            "pty", "ctypes", "socket", "urllib", "requests", "importlib"
        ]

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # 1. Imports check
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        base_module = alias.name.split('.')[0]
                        if base_module in forbidden_modules:
                            return f"'{alias.name}' modülünün yüklenmesine izin verilmiyor."
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        base_module = node.module.split('.')[0]
                        if base_module in forbidden_modules:
                            return f"'{node.module}' modülünden import yapılmasına izin verilmiyor."

                # 2. Block access to builtins and magic variables by name
                elif isinstance(node, ast.Name):
                    if node.id in forbidden_builtins:
                        return f"'{node.id}' fonksiyonu/değişkeninin kullanılması yasaktır."
                    if node.id.startswith("_") or "__" in node.id:
                        return f"Gizli veya özel isimlerin ('{node.id}') kullanılması yasaktır."

                # 3. Block double-underscores (dunder) / private attributes access
                elif isinstance(node, ast.Attribute):
                    if node.attr.startswith("_") or "__" in node.attr:
                        return f"'{node.attr}' özniteliğine erişim yasaktır."
                    if node.attr in forbidden_builtins:
                        return f"'{node.attr}' fonksiyonuna erişim yasaktır."

        except Exception as e:
            return f"Kod sözdizimi doğrulanırken hata oluştu: {str(e)}"

        # 4. Fallback string checks for dangerous words
        for kw in unsafe_keywords:
            if kw in code:
                return f"'{kw}' ifadesinin kullanılmasına izin verilmiyor."
                
        return None

    def run_pandas_code(self, code: str, file_mappings: Dict[str, str]) -> Dict[str, Any]:
        """
        Executes pandas analysis code on given file mappings.
        file_mappings: e.g. {"satislar": "c:/path/to/satislar.xlsx"}
        The code can reference a DataFrame named `satislar` directly in its namespace.
        The result should be assigned to a variable named `result` (DataFrame, list, dict, or value).
        A Plotly figure can be assigned to a variable named `fig` (Plotly Figure).
        """
        # Perform dynamic security validation check
        safety_error = self._check_code_safety(code)
        if safety_error:
            return {"error": f"⚠️ Sandbox Güvenlik Kısıtlaması: {safety_error}"}

        # Create a temporary file to hold the runner script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            runner_path = f.name
            
        try:
            # Build the runner code
            runner_code = self._generate_runner_code(code, file_mappings)
            with open(runner_path, 'w', encoding='utf-8') as f:
                f.write(runner_code)
                
            # Execute in a subprocess
            res = subprocess.run(
                [sys.executable, runner_path],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                encoding='utf-8'
            )
            
            if res.returncode == 0:
                try:
                    return json.loads(res.stdout.strip())
                except Exception as e:
                    return {"error": f"Sandbox çıktısı ayrıştırılamadı: {res.stdout.strip()} (Hata: {str(e)})"}
            else:
                # Subprocess exited with non-zero code
                err_msg = res.stderr.strip() or res.stdout.strip() or "Bilinmeyen çalışma zamanı hatası."
                try:
                    parsed = json.loads(err_msg)
                    if isinstance(parsed, dict) and "error" in parsed:
                        return parsed
                except Exception:
                    pass
                return {"error": err_msg}
                
        except subprocess.TimeoutExpired:
            return {"error": f"Süre sınırı ({self.timeout_seconds} saniye) aşıldı."}
        except Exception as e:
            return {"error": f"Sandbox yürütme hatası: {str(e)}"}
        finally:
            if os.path.exists(runner_path):
                try:
                    os.remove(runner_path)
                except Exception:
                    pass

    def _generate_runner_code(self, code: str, file_mappings: Dict[str, str]) -> str:
        runner_template = f"""# -*- coding: utf-8 -*-
import os
import sys
import json
import numpy as np
import pandas as pd

try:
    import plotly
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

def run_isolated():
    file_mappings = {repr(file_mappings)}
    user_code = {repr(code)}
    
    # Load dataframes into context
    locs = {{}}
    for df_name, file_path in file_mappings.items():
        if not file_path or not os.path.exists(file_path):
            continue
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ('.xlsx', '.xls'):
                locs[df_name] = pd.read_excel(file_path)
            elif ext == '.tsv':
                locs[df_name] = pd.read_csv(file_path, sep='\\t')
            else:
                locs[df_name] = pd.read_csv(file_path)
        except Exception as e:
            print(json.dumps({{"error": f"Veri dosyası {{df_name}} yüklenemedi: {{str(e)}}"}}))
            return
            
    locs["result"] = None
    locs["fig"] = None
    
    # Inject libraries for convenience
    locs["pd"] = pd
    locs["np"] = np
    if HAS_PLOTLY:
        locs["plotly"] = plotly
        locs["px"] = px
        locs["go"] = go

    try:
        exec(user_code, globals(), locs)
    except Exception as e:
        import traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        # Exclude the wrapper framework traceback lines
        tb_clean = [line for line in tb_lines if "exec(user_code" not in line and "run_isolated" not in line]
        print(json.dumps({{"error": "".join(tb_clean)}}))
        return

    result_val = locs.get("result")
    fig_val = locs.get("fig")
    
    output = {{"data": None, "visualization": None}}
    
    # Auto-convert dict/list-of-dict results to tabular format for UI
    if result_val is not None and not isinstance(result_val, (pd.DataFrame, pd.Series)):
        try:
            if isinstance(result_val, list) and len(result_val) > 0 and isinstance(result_val[0], dict):
                result_val = pd.DataFrame(result_val)
            elif isinstance(result_val, dict):
                records_key = None
                for k, v in result_val.items():
                    if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                        records_key = k
                        break
                if records_key is not None:
                    df_extracted = pd.DataFrame(result_val[records_key])
                    meta_metrics = {{k: v for k, v in result_val.items() if k != records_key}}
                    result_val = df_extracted
                    output["metrics"] = meta_metrics
                else:
                    if all(isinstance(v, (int, float, str, bool)) or v is None for v in result_val.values()):
                        result_val = pd.DataFrame(list(result_val.items()), columns=['Özellik / Metrik', 'Değer'])
        except Exception:
            pass

    if result_val is not None:
        if isinstance(result_val, pd.DataFrame):
            df_slice = result_val.head(5000)
            df_slice = df_slice.replace({{np.nan: None}})
            output["data"] = {{
                "columns": list(df_slice.columns),
                "index": list(df_slice.index),
                "rows": df_slice.values.tolist(),
                "row_count": len(result_val)
            }}
        elif isinstance(result_val, pd.Series):
            series_slice = result_val.head(5000)
            series_slice = series_slice.replace({{np.nan: None}})
            output["data"] = {{
                "columns": [result_val.name or "value"],
                "index": list(series_slice.index),
                "rows": [[v] for v in series_slice.values.tolist()],
                "row_count": len(result_val)
            }}
        elif isinstance(result_val, (dict, list, int, float, str, bool)):
            output["data"] = {{
                "value": result_val
            }}
        else:
            output["data"] = {{
                "value": str(result_val)
            }}
            
    # Process Plotly figure
    if fig_val is not None:
        try:
            if HAS_PLOTLY and isinstance(fig_val, plotly.graph_objs._figure.Figure):
                output["visualization"] = json.loads(fig_val.to_json())
            else:
                output["visualization_error"] = "fig değişkeni geçerli bir Plotly Figure objesi değil."
        except Exception as e:
            output["visualization_error"] = f"Grafik serileştirme hatası: {{str(e)}}"
            
    print(json.dumps(output))

if __name__ == "__main__":
    run_isolated()
"""
        return runner_template
