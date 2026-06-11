import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from translator_engine import TranslatorEngine
import os
import json

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Universal Game Translator Plus v2.0 — by NodNuatTranslator")
        self.geometry("900x700")

        self.engine = TranslatorEngine(log_callback=self.update_log, progress_callback=self.update_progress)
        self.config_file = "config.json"
        self._fix_mode = False
        
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)  # Settings/Glossary row expands
        self.grid_rowconfigure(2, weight=1)  # Log expands

        # 1. File Selection Frame
        file_frame = ctk.CTkFrame(self)
        file_frame.grid(row=0, column=0, columnspan=2, padx=20, pady=10, sticky="ew")
        file_frame.grid_columnconfigure(0, weight=1)  # Input entry expands

        ctk.CTkLabel(file_frame, text="1. Select Files", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w", columnspan=5)

        # Row 1: Input + Browse (right)
        self.input_file_var = tk.StringVar()
        ctk.CTkEntry(file_frame, textvariable=self.input_file_var, placeholder_text="Select input file...").grid(row=1, column=0, padx=(10, 5), pady=(0, 5), sticky="ew")
        ctk.CTkButton(file_frame, text="Browse", width=80, command=self.browse_input).grid(row=1, column=1, padx=5, pady=(0, 5))

        # Row 2: Output + Format + Convert/Restore/Clear (right)
        self.output_file_var = tk.StringVar(value="output_translated.csv")
        ctk.CTkEntry(file_frame, textvariable=self.output_file_var, placeholder_text="Output file...").grid(row=2, column=0, padx=(10, 5), pady=(0, 10), sticky="ew")

        self.convert_format_var = ctk.StringVar(value="Auto-detect")
        ctk.CTkOptionMenu(file_frame, variable=self.convert_format_var, width=170,
                          values=["Auto-detect", "CSV/TSV (delimited)", "CSV 3-col (key,source,trans)", "TXT (one per line)", "XML (game stringtable)", "Subtitles (untranslated only)", "Fix garbled text (AI)"]).grid(row=2, column=1, padx=5, pady=(0, 10))

        ctk.CTkButton(file_frame, text="Convert", width=75, fg_color="#1565C0", command=self.convert_file).grid(row=2, column=2, padx=(10, 2), pady=(0, 10))
        ctk.CTkButton(file_frame, text="Restore", width=75, fg_color="#6A1B9A", command=self.restore_file).grid(row=2, column=3, padx=2, pady=(0, 10))
        ctk.CTkButton(file_frame, text="Clear", width=50, fg_color="#37474F", hover_color="#455A64", command=self.clear_files).grid(row=2, column=4, padx=(2, 10), pady=(0, 10))

        # 2. Settings Frame
        settings_frame = ctk.CTkFrame(self)
        settings_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        settings_frame.grid_columnconfigure(1, weight=1)  # Entry column expands

        ctk.CTkLabel(settings_frame, text="2. API Settings", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        ctk.CTkLabel(settings_frame, text="API Key:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.api_key_var = tk.StringVar()
        ctk.CTkEntry(settings_frame, textvariable=self.api_key_var).grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(settings_frame, text="Model:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.model_var = ctk.StringVar(value="gemini-3.5-flash")
        
        all_models = [
            # Google Gemini (2025-2026)
            "gemini-3.5-flash", "gemini-3.1-pro", "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash",
            # DeepSeek (2025-2026)
            "deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner",
            # Anthropic Claude (2025-2026)
            "claude-opus-4.7", "claude-sonnet-4.6", "claude-haiku-4.5", "claude-3-5-sonnet-20241022",
            # OpenAI / Local
            "gpt-4o", "gpt-4o-mini", "o1-mini", "o3-mini", "custom-local-llm"
        ]
        
        ctk.CTkOptionMenu(settings_frame, variable=self.model_var, values=all_models).grid(row=2, column=1, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(settings_frame, text="Base URL (Local LLM):").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.base_url_var = tk.StringVar(value="http://localhost:1234/v1/chat/completions")
        ctk.CTkEntry(settings_frame, textvariable=self.base_url_var).grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(settings_frame, text="Custom Model Name:").grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.custom_model_var = tk.StringVar(value="llama-3-8b")
        ctk.CTkEntry(settings_frame, textvariable=self.custom_model_var).grid(row=4, column=1, padx=10, pady=5, sticky="ew")

        # 3. Glossary Frame
        glossary_frame = ctk.CTkFrame(self)
        glossary_frame.grid(row=1, column=1, padx=20, pady=10, sticky="nsew")
        glossary_frame.grid_columnconfigure(0, weight=1)
        glossary_frame.grid_rowconfigure(4, weight=1)  # Textbox row expands

        ctk.CTkLabel(glossary_frame, text="3. Glossary & Prompt", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")

        ctk.CTkLabel(glossary_frame, text="Canary Words (comma separated):").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.canary_var = tk.StringVar()
        ctk.CTkEntry(glossary_frame, textvariable=self.canary_var).grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(glossary_frame, text="Custom Glossary (e.g. Sword=ดาบ):").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.glossary_text = ctk.CTkTextbox(glossary_frame)
        self.glossary_text.grid(row=4, column=0, padx=10, pady=(5, 10), sticky="nsew")

        # 4. Log/Terminal Frame
        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=2, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        self.log_box = ctk.CTkTextbox(log_frame, state="disabled", fg_color="black", text_color="lightgreen", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # 5. Action Buttons
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=3, column=0, columnspan=2, padx=20, pady=10, sticky="ew")

        self.status_label = ctk.CTkLabel(action_frame, text="● Ready", text_color="#6B7280", font=ctk.CTkFont(size=13))
        self.status_label.pack(side="left", padx=(0, 10))

        self.start_btn = ctk.CTkButton(action_frame, text="Analyze & Translate", command=self.start_translation, width=200, height=40, font=ctk.CTkFont(size=14, weight="bold"))
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn = ctk.CTkButton(action_frame, text="Stop", command=self.stop_translation, fg_color="#DC2626", hover_color="#991B1B", width=100, height=40, state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        self.progress_bar = ctk.CTkProgressBar(action_frame)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(20, 5))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(action_frame, text="0%", width=45, font=ctk.CTkFont(size=13))
        self.progress_label.pack(side="left", padx=(0, 5))

    def update_log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def update_progress(self, val):
        self.progress_bar.set(val)
        pct = int(val * 100)
        self.progress_label.configure(text=f"{pct}%")
        if val >= 1.0:
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.status_label.configure(text="● Complete", text_color="#10B981")

    def clear_files(self):
        self.input_file_var.set("")
        self.output_file_var.set("output_translated.csv")
        self.update_log("Input/output fields cleared.")

    def browse_input(self):
        fmt = self.convert_format_var.get()
        if fmt == "XML (game stringtable)":
            filetypes = [("XML files", "*.xml"), ("All files", "*.*")]
        elif fmt in ("TXT (one per line)", "Subtitles (untranslated only)", "Fix garbled text (AI)"):
            filetypes = [("Text files", "*.txt"), ("All files", "*.*")]
        else:
            filetypes = [("CSV/TSV files", "*.csv;*.tsv;*.txt"), ("All files", "*.*")]
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            self.input_file_var.set(filename)
            if not self.output_file_var.get() or self.output_file_var.get() == "output_translated.csv":
                base, ext = os.path.splitext(filename)
                self.output_file_var.set(f"{base}_translated{ext}")

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    api_data = data.get("api_settings", {})
                    self.api_key_var.set(api_data.get("api_key", ""))
                    self.model_var.set(api_data.get("model", "deepseek-chat"))
                    self.base_url_var.set(api_data.get("base_url", "http://localhost:1234/v1/chat/completions"))
                    self.custom_model_var.set(api_data.get("custom_model", "llama-3-8b"))

                    file_data = data.get("file_settings", {})
                    self.input_file_var.set(file_data.get("input_csv", ""))
                    self.output_file_var.set(file_data.get("output_csv", "output_translated.csv"))

                    safe_data = data.get("safety_settings", {})
                    self.canary_var.set(", ".join(safe_data.get("canary_words", [])))

                    glossary = data.get("glossary", "")
                    if glossary:
                        self.glossary_text.insert("1.0", glossary)
            except:
                pass

        if not self.api_key_var.get():
            model = self.model_var.get()
            env_prefix_map = {
                "gemini": "GEMINI_API_KEY",
                "claude": "ANTHROPIC_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
            }
            for prefix, env_var in env_prefix_map.items():
                if model.startswith(prefix):
                    env_key = os.environ.get(env_var, "")
                    if env_key:
                        self.api_key_var.set(env_key)
                        break
            if not self.api_key_var.get():
                env_key = os.environ.get("OPENAI_API_KEY", "")
                if env_key:
                    self.api_key_var.set(env_key)

        sys_prompt_file = "system_prompt.txt"
        if os.path.exists(sys_prompt_file):
            try:
                with open(sys_prompt_file, 'r', encoding='utf-8') as f:
                    self.sys_prompt_base = f.read().strip()
            except:
                self.sys_prompt_base = "I want you to act as a Master-Level English-to-Thai Video Game Localization Specialist.\n1. PRESERVE VARIABLES: Any placeholders like [TAG_0], {0}, etc. MUST remain exactly intact.\n2. EXACT OUTPUT FORMAT: ID\\tTHAI_TRANSLATION"
        else:
            self.sys_prompt_base = "I want you to act as a Master-Level English-to-Thai Video Game Localization Specialist.\n1. PRESERVE VARIABLES: Any placeholders like [TAG_0], {0}, etc. MUST remain exactly intact.\n2. EXACT OUTPUT FORMAT: ID\\tTHAI_TRANSLATION"

    def save_config(self):
        data = {
            "api_settings": {
                "api_key": self.api_key_var.get(),
                "model": self.model_var.get(),
                "base_url": self.base_url_var.get(),
                "custom_model": self.custom_model_var.get()
            },
            "file_settings": {
                "input_csv": self.input_file_var.get(),
                "output_csv": self.output_file_var.get()
            },
            "safety_settings": {
                "canary_words": [w.strip() for w in self.canary_var.get().split(",") if w.strip()]
            },
            "glossary": self.glossary_text.get("1.0", "end-1c")
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def convert_file(self):
        input_path = self.input_file_var.get()
        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("Error", "Please select an input file first.")
            return

        base, _ = os.path.splitext(input_path)
        output_path = f"{base}_standard.csv"

        fmt = self.convert_format_var.get()
        force_delim = None
        if fmt == "TXT (one per line)":
            force_delim = "newline"
        elif fmt == "Subtitles (untranslated only)":
            force_delim = "subtitles"
        elif fmt == "CSV 3-col (key,source,trans)":
            force_delim = "csv3col"
        elif fmt == "XML (game stringtable)":
            force_delim = "xml"
        elif fmt == "Fix garbled text (AI)":
            force_delim = "newline"
            self._fix_mode = True

        if fmt == "Fix garbled text (AI)":
            self.update_log("Fix mode: will use system_prompt_fix.txt for AI text cleanup.")

        self.update_log(f"Converting file to standard format (mode: {fmt})...")
        result_path, mapping_path = self.engine.convert_to_standard(input_path, output_path, force_delim=force_delim)

        if result_path:
            self.input_file_var.set(result_path)
            self.output_file_var.set(f"{base}_translated.csv")
            self.update_log(f"Done. Now click 'Analyze & Translate' to translate this file.")
            messagebox.showinfo("Converted", f"File converted:\n{result_path}\n\nThis file is ready for translation.\nAfter translation, use 'Restore' to convert back.")

    def restore_file(self):
        translated_path = self.output_file_var.get()
        if not translated_path or not os.path.exists(translated_path):
            messagebox.showerror("Error", "Translated output file not found. Run translation first.")
            return

        # Find mapping file next to standard CSV input
        input_path = self.input_file_var.get()
        mapping_path = input_path + ".mapping.json"

        if not os.path.exists(mapping_path):
            # Try next to output
            mapping_path = translated_path + ".mapping.json"
        if not os.path.exists(mapping_path):
            messagebox.showerror("Error", f"Mapping file not found:\n{mapping_path}\n\nMake sure you converted the original file first.")
            return

        # Derive restored filename from original file, not from translated chain
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                mapping_meta = json.load(f)
            orig_file = mapping_meta.get("original_file", translated_path)
        except Exception:
            orig_file = translated_path
        orig_base, orig_ext = os.path.splitext(orig_file)
        out = f"{orig_base}_restored{orig_ext}"

        self.update_log("Restoring to original format...")
        result = self.engine.restore_from_standard(translated_path, mapping_path, out)

        if result:
            self.update_log(f"Restored file: {result}")
            messagebox.showinfo("Restored", f"File restored to original format:\n{result}")

    def start_translation(self):
        self.save_config()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)
        self.progress_label.configure(text="0%")
        self.status_label.configure(text="● Translating…", text_color="#F59E0B")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        # Auto-switch to fix prompt if Fix garbled text mode was used
        if self._fix_mode:
            fix_prompt_file = "system_prompt_fix.txt"
            if os.path.exists(fix_prompt_file):
                try:
                    with open(fix_prompt_file, 'r', encoding='utf-8') as f:
                        self.sys_prompt_base = f.read().strip()
                    self.update_log("Using system_prompt_fix.txt for text cleanup mode.")
                except Exception:
                    pass
            self._fix_mode = False

        self.update_log("Starting Analysis & Translation...")

        config = {
            "api_key": self.api_key_var.get(),
            "model": self.model_var.get(),
            "base_url": self.base_url_var.get(),
            "custom_model": self.custom_model_var.get(),
            "input_csv": self.input_file_var.get(),
            "output_csv": self.output_file_var.get(),
            "canary_words": self.canary_var.get(),
            "glossary": self.glossary_text.get("1.0", "end-1c"),
            "system_prompt": self.sys_prompt_base
        }
        
        self.engine.run_translation(config)

    def stop_translation(self):
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="● Stopping…", text_color="#EF4444")
        self.engine.stop_translation()

if __name__ == "__main__":
    app = TranslatorApp()
    app.mainloop()
