# -*- coding: utf-8 -*-
import os
import re
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import math
import sys
import traceback

# Pillow import
try:
    from PIL import Image, ImageFile, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageTk = None
    PIL_AVAILABLE = False

# --- 辅助函数 ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

# --- 核心逻辑函数 (自然排序) ---
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]

# --- 核心逻辑函数 (图像合并) ---
def create_sprite_sheet(input_dir, columns, rows, output_path, status_callback,
                        frame_width, frame_height, image_mode,
                        sorted_image_files, resize_output):
    status_callback(f"开始合并: 网格={columns}x{rows}, 单帧={frame_width}x{frame_height}")
    try:
        file_count = len(sorted_image_files)
        if file_count == 0:
             status_callback("错误：没有找到需要合并的图像文件。")
             return False
        status_callback(f"使用 {file_count} 个已排序图像文件。")

        total_width = frame_width * columns
        total_height = frame_height * rows
        status_callback(f"创建序列图画布: {total_width}x{total_height} (模式: {image_mode})")

        try:
            sprite_sheet = Image.new(image_mode, (total_width, total_height))
        except ValueError as ve:
            status_callback(f"警告：图像模式 '{image_mode}' 无效 ({ve})，尝试使用 'RGBA'。")
            try:
                image_mode = 'RGBA'
                sprite_sheet = Image.new(image_mode, (total_width, total_height))
            except Exception as fallback_e:
                 status_callback(f"错误：无法创建图像画布: {fallback_e}")
                 return False

        max_images = columns * rows
        processed_count = 0
        for i, filename in enumerate(sorted_image_files):
            if i >= max_images:
                status_callback(f"信息：图像数量 ({file_count}) 超出网格容量 ({max_images})，已停止处理多余帧。")
                break

            current_col = i % columns
            current_row = i // columns
            paste_x = current_col * frame_width
            paste_y = current_row * frame_height
            image_path = os.path.join(input_dir, filename)
            try:
                 with Image.open(image_path) as img:
                     img_to_paste = img
                     if img.size != (frame_width, frame_height):
                         status_callback(f"信息：调整图像 {filename} 的尺寸...")
                         img_to_paste = img.resize((frame_width, frame_height), Image.Resampling.LANCZOS)
                     if img_to_paste.mode != image_mode:
                         status_callback(f"信息：转换图像 {filename} 的模式...")
                         try:
                            img_to_paste = img_to_paste.convert(image_mode)
                         except Exception as convert_e:
                            status_callback(f"警告：转换图像 {filename} 模式失败: {convert_e}。")
                     sprite_sheet.paste(img_to_paste, (paste_x, paste_y))
                     processed_count += 1
            except FileNotFoundError:
                 status_callback(f"错误：无法找到图像文件 {filename}，已跳过。")
                 continue
            except Exception as paste_e:
                 status_callback(f"错误：处理或粘贴图像 {filename} 时出错: {paste_e}，已跳过。")
                 continue

        status_callback(f"已处理 {processed_count} 张图像。")

        final_image_to_save = sprite_sheet
        if resize_output:
            status_callback(f"检测到压缩选项：正在将图像从 {total_width}x{total_height} 压缩到 {frame_width}x{frame_height}...")
            try:
                final_image_to_save = sprite_sheet.resize((frame_width, frame_height), Image.Resampling.LANCZOS)
                status_callback("压缩完成。")
            except Exception as resize_e:
                status_callback(f"错误：压缩图像时出错: {resize_e}。将尝试保存原始大图。")
                final_image_to_save = sprite_sheet

        try:
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                 os.makedirs(output_dir)
                 status_callback(f"已创建输出目录: {output_dir}")
            final_image_to_save.save(output_path)
            if resize_output and final_image_to_save != sprite_sheet:
                 status_callback(f"成功！压缩后的序列图已保存至: {output_path}")
            else:
                 status_callback(f"成功！序列图已保存至: {output_path}")
            return True
        except Exception as save_e:
            status_callback(f"错误：保存最终序列图到 {output_path} 时失败: {save_e}")
            return False

    except Exception as e:
        status_callback(f"合并核心逻辑时发生未预料的错误: {e}")
        # 保留核心逻辑的日志记录
        try:
            with open("core_logic_error.log", "w", encoding='utf-8') as f:
                f.write(f"create_sprite_sheet 错误:\n{traceback.format_exc()}")
            status_callback("错误详情已记录到 core_logic_error.log")
        except Exception as log_e:
             status_callback(f"写入核心逻辑错误日志失败: {log_e}")
        return False


# --- 自定义确认对话框类 ---
class ConfirmationDialog(tk.Toplevel):
    def __init__(self, parent, title, message, file_count, original_settings, recommended_settings):
        super().__init__(parent)
        self.transient(parent); self.grab_set(); self.result = None; self.title(title); self.resizable(False, False);
        self.file_count = file_count; self.original_cols, self.original_rows = original_settings; self.recommended_cols, self.recommended_rows = recommended_settings;
        main_frame = ttk.Frame(self, padding="10 10 10 10"); main_frame.pack(expand=True, fill="both"); msg_label = ttk.Label(main_frame, text=message, wraplength=400, justify=tk.LEFT); msg_label.pack(pady=(0, 15)); button_frame = ttk.Frame(main_frame); button_frame.pack(fill=tk.X, pady=5);
        rec_text = f"使用推荐 ({self.recommended_cols}x{self.recommended_rows})"; rec_button = ttk.Button(button_frame, text=rec_text, command=self.on_recommended); rec_button.pack(side=tk.LEFT, expand=True, padx=5); orig_text = f"使用当前 ({self.original_cols}x{self.original_rows})"; orig_button = ttk.Button(button_frame, text=orig_text, command=self.on_original); orig_button.pack(side=tk.LEFT, expand=True, padx=5); cancel_button = ttk.Button(button_frame, text="取消", command=self.on_cancel); cancel_button.pack(side=tk.LEFT, expand=True, padx=5);
        self.protocol("WM_DELETE_WINDOW", self.on_cancel); self.update_idletasks();
        try:
            parent_x, parent_y = parent.winfo_rootx(), parent.winfo_rooty(); parent_width, parent_height = parent.winfo_width(), parent.winfo_height(); dialog_width, dialog_height = self.winfo_width(), self.winfo_height();
            if parent_width > 0 and parent_height > 0 and dialog_width > 0 and dialog_height > 0: x = parent_x + (parent_width // 2) - (dialog_width // 2); y = parent_y + (parent_height // 2) - (dialog_height // 2); self.geometry(f'+{x}+{y}')
            else: self.geometry("+300+300")
        except Exception as e:
            print(f"警告：居中 ConfirmationDialog 时出错: {e}")
            self.geometry("+300+300")
    def on_recommended(self): self.result = "recommended"; self.destroy()
    def on_original(self): self.result = "original"; self.destroy()
    def on_cancel(self): self.result = "cancel"; self.destroy()


# --- GUI 应用类 ---
class SpriteSheetApp:
    def __init__(self, master):
        self.master = master
        master.title("序列图合并工具")
        master.geometry("600x470")
        master.minsize(500, 420)
        self.input_dir = tk.StringVar(); self.output_path = tk.StringVar(); self.columns_var = tk.StringVar(value="10"); self.rows_var = tk.StringVar(value="1"); self.resize_var = tk.BooleanVar(value=False);
        try:
            style = ttk.Style(); available_themes = style.theme_names(); preferred_themes = ['vista', 'xpnative', 'clam', 'alt', 'default'];
            for theme in preferred_themes:
                if theme in available_themes:
                    try: style.theme_use(theme); break
                    except: pass
            style.configure("TLabel", padding=5); style.configure("TButton", padding=5); style.configure("TEntry", padding=5); style.configure("TCheckbutton", padding=(0, 5))
        except Exception as e: print(f"警告：应用 ttk 样式时出错: {e}")
        try:
            main_frame = ttk.Frame(master, padding="10 10 10 10"); main_frame.pack(fill=tk.BOTH, expand=True); main_frame.columnconfigure(1, weight=1);
            ttk.Label(main_frame, text="输入帧目录:").grid(row=0, column=0, sticky=tk.W); self.input_entry = ttk.Entry(main_frame, textvariable=self.input_dir, width=50, state='readonly'); self.input_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 5)); self.input_button = ttk.Button(main_frame, text="选择...", command=self.select_input_dir); self.input_button.grid(row=0, column=2, sticky=tk.E);
            options_frame = ttk.Frame(main_frame); options_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5); ttk.Label(options_frame, text="列数:").pack(side=tk.LEFT, padx=(0, 5)); self.columns_entry = ttk.Entry(options_frame, textvariable=self.columns_var, width=5); self.columns_entry.pack(side=tk.LEFT, padx=(0, 15)); ttk.Label(options_frame, text="行数:").pack(side=tk.LEFT, padx=(0, 5)); self.rows_entry = ttk.Entry(options_frame, textvariable=self.rows_var, width=5); self.rows_entry.pack(side=tk.LEFT);
            self.resize_check = ttk.Checkbutton(main_frame, text="将最终输出压缩到单帧大小 (可能降低质量)", variable=self.resize_var, onvalue=True, offvalue=False); self.resize_check.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(5, 0));
            ttk.Label(main_frame, text="输出文件路径:").grid(row=3, column=0, sticky=tk.W); self.output_entry = ttk.Entry(main_frame, textvariable=self.output_path, width=50, state='readonly'); self.output_entry.grid(row=3, column=1, sticky=tk.EW, padx=(0, 5)); self.output_button = ttk.Button(main_frame, text="保存为...", command=self.select_output_file); self.output_button.grid(row=3, column=2, sticky=tk.E);
            self.run_button = ttk.Button(main_frame, text="开始合并", command=self.start_processing); self.run_button.grid(row=4, column=0, columnspan=3, pady=15);
            ttk.Label(main_frame, text="状态信息:").grid(row=5, column=0, sticky=tk.W); self.status_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD, state='disabled'); self.status_text.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(5, 0)); main_frame.rowconfigure(6, weight=1);
        except Exception as e: # <--- 这是捕获控件创建错误的 except 块
            # ---> except 块内部的代码需要缩进 <---
            messagebox.showerror("初始化错误", f"创建界面时发生严重错误:\n{e}")
            # 下面这行大约是 179 行，它的缩进必须与上面的 messagebox 对齐
            if master: # 检查 master 是否存在（理论上应该存在）
                master.destroy() # 尝试关闭窗口
            # raise SystemExit 也应该与 messagebox 和 if 对齐
            raise SystemExit(f"GUI 初始化失败: {e}") # 抛出异常退出程序
        # --- try...except 块结束 ---

    def select_input_dir(self):
        directory = filedialog.askdirectory(title="选择包含序列帧的目录");
        if directory:
            self.input_dir.set(directory);
            if not self.output_path.get():
                base = os.path.basename(directory); safe_base = "".join(c for c in base if c.isalnum() or c in ('_', '-')).rstrip();
                if not safe_base: safe_base = "output";
                suggested_out = os.path.join(os.path.dirname(directory), f"{safe_base}_spritesheet.png"); self.output_path.set(suggested_out)

    def select_output_file(self):
        initial_dir = os.path.dirname(self.input_dir.get()) if self.input_dir.get() else "."; initial_file = os.path.basename(self.output_path.get()) if self.output_path.get() else "spritesheet.png";
        filepath = filedialog.asksaveasfilename(title="选择序列图保存位置和名称", initialdir=initial_dir, initialfile=initial_file, defaultextension=".png", filetypes=[("PNG 文件", "*.png"), ("JPEG 文件", "*.jpg;*.jpeg"), ("BMP 文件", "*.bmp"), ("所有文件", "*.*")]);
        if filepath: self.output_path.set(filepath)

    def update_status(self, message):
        if self.master and hasattr(self, 'status_text') and self.status_text: self.master.after(0, self._update_status_ui, message)
        else: print(f"STATUS (window closed?): {message}")

    def _update_status_ui(self, message):
        try: self.status_text.config(state='normal'); self.status_text.insert(tk.END, message + "\n"); self.status_text.see(tk.END); self.status_text.config(state='disabled')
        except Exception as e: print(f"警告：更新状态文本时出错: {e}")

    def _toggle_controls(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED; readonly_state = 'normal' if enabled else 'readonly';
        try:
            if hasattr(self, 'input_button'): self.input_button.config(state=state)
            if hasattr(self, 'output_button'): self.output_button.config(state=state)
            if hasattr(self, 'columns_entry'): self.columns_entry.config(state=readonly_state)
            if hasattr(self, 'rows_entry'): self.rows_entry.config(state=readonly_state)
            if hasattr(self, 'run_button'): self.run_button.config(state=state)
            if hasattr(self, 'resize_check'): self.resize_check.config(state=state)
        except Exception as e: print(f"警告：切换控件状态时出错: {e}")

    def start_processing(self):
        in_dir = self.input_dir.get(); out_path = self.output_path.get(); cols_str = self.columns_var.get(); rows_str = self.rows_var.get(); should_resize_output = self.resize_var.get();
        if not PIL_AVAILABLE: messagebox.showerror("错误", "缺少 Pillow 库，无法进行图像处理。\n请安装 Pillow (pip install Pillow)。"); return
        if not in_dir or not os.path.isdir(in_dir): messagebox.showerror("错误", f"请选择一个有效的输入帧目录！\n当前路径: '{in_dir}'"); return
        if not out_path: messagebox.showerror("错误", "请指定输出文件路径！"); return

        # --- 行列数转换与验证 ---
        try:
            original_cols = int(cols_str)
            original_rows = int(rows_str)
            if original_cols <= 0 or original_rows <= 0:
                raise ValueError("行列数必须是正整数")
        except ValueError as ve:
            messagebox.showerror("错误", f"列数和行数必须是有效的正整数！\n当前值: 列='{cols_str}', 行='{rows_str}'\n({ve})")
            return
        # --- 行列数转换结束 ---

        # --- 扫描文件并获取首帧信息 ---
        frame_width, frame_height, image_mode = None, None, None; sorted_image_files = []; file_count = 0
        try:
            self.update_status(f"正在扫描目录: {in_dir}")
            all_files = [f for f in os.listdir(in_dir) if os.path.isfile(os.path.join(in_dir, f))]
            image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tif', '.tiff'}
            image_files = [f for f in all_files if os.path.splitext(f)[1].lower() in image_extensions]
            if not image_files:
                messagebox.showwarning("警告", f"在输入目录 '{in_dir}' 中未找到任何支持的图像文件。")
                return
            image_files.sort(key=natural_sort_key)
            sorted_image_files = image_files
            file_count = len(sorted_image_files)
            self.update_status(f"找到 {file_count} 个图像文件。已排序。")

            first_image_path = os.path.join(in_dir, sorted_image_files[0])
            with Image.open(first_image_path) as first_img:
                frame_width, frame_height = first_img.size
                image_mode = first_img.mode
                if not frame_width or not frame_height or frame_width <= 0 or frame_height <= 0:
                    raise ValueError(f"从 {sorted_image_files[0]} 获取的帧尺寸无效: {frame_width}x{frame_height}")

        except FileNotFoundError:
             messagebox.showerror("错误", f"输入目录未找到: {in_dir}")
             self.update_status(f"错误：输入目录未找到 {in_dir}")
             return
        except Exception as e:
             # 处理扫描/打开文件时的其他错误
             print(f"!!! 扫描文件或打开首帧时出错: {e}") # 打印原始错误
             try:
                 # 尝试记录日志
                 with open("scan_error.log", "w", encoding='utf-8') as f:
                     f.write(f"扫描文件或打开首帧错误:\n{traceback.format_exc()}")
                 # 显示带日志提示的消息框
                 messagebox.showerror("错误", f"扫描文件或读取首帧信息时发生错误:\n{e}\n详情已记录到 scan_error.log")
             except Exception as log_e:
                 # 如果日志也失败，显示基本消息框
                 print(f"!!! 记录扫描错误日志时也出错: {log_e}")
                 try:
                     messagebox.showerror("错误", f"扫描文件或读取首帧信息时发生错误:\n{e}")
                 except:
                     pass # 连消息框都失败就算了
             self.update_status(f"扫描或读取首帧时出错: {e}")
             return
        # --- 扫描文件结束 ---


        grid_capacity = original_cols * original_rows; current_cols, current_rows = original_cols, original_rows; recommended_cols, recommended_rows = original_cols, original_rows
        if file_count != grid_capacity:
            recommended_cols = math.ceil(math.sqrt(file_count)); recommended_rows = math.ceil(file_count / recommended_cols);
            if file_count > grid_capacity: title = "警告：可能丢失帧"; message = (f"找到 {file_count} 个图像文件，但当前设置 ({original_cols}x{original_rows}) 只能容纳 {grid_capacity} 个。\n\n如果使用当前设置，后面的 **{file_count - grid_capacity}** 个序列帧将被丢失。\n\n建议设置为 {recommended_cols}x{recommended_rows} 以包含所有文件。\n\n请选择操作：")
            else: title = "警告：可能产生空白帧"; message = (f"找到 {file_count} 个图像文件，但当前设置 ({original_cols}x{original_rows}) 容量为 {grid_capacity}。\n\n如果使用当前设置，将在序列图末尾产生 **{grid_capacity - file_count}** 个空白帧。\n\n建议设置为 {recommended_cols}x{recommended_rows} 以正好匹配文件数。\n\n请选择操作：")
            dialog = ConfirmationDialog(self.master, title=title, message=message, file_count=file_count, original_settings=(original_cols, original_rows), recommended_settings=(recommended_cols, recommended_rows))
            self.master.wait_window(dialog);
            if dialog.result == "cancel" or dialog.result is None: self.update_status("操作已取消。"); return
            elif dialog.result == "recommended": current_cols, current_rows = recommended_cols, recommended_rows; self.columns_var.set(str(current_cols)); self.rows_var.set(str(current_rows)); self.update_status(f"已采纳推荐设置: {current_cols}x{current_rows}")

        try:
            if not frame_width or not frame_height or frame_width <= 0 or frame_height <= 0: raise ValueError("单帧尺寸无效")
            final_total_width = frame_width * current_cols; final_total_height = frame_height * current_rows; MAX_DIMENSION = 16384; proceed_large = True
            if final_total_width > MAX_DIMENSION or final_total_height > MAX_DIMENSION:
                rec_cols_check = math.ceil(math.sqrt(file_count)); rec_rows_check = math.ceil(file_count / rec_cols_check);
                recommended_width_approx = frame_width * rec_cols_check; recommended_height_approx = frame_height * rec_rows_check
                warn_message = (f"警告：计算出的最终序列图尺寸为 {final_total_width}x{final_total_height} 像素，这非常大！\n\n创建如此大的图像可能会消耗大量内存和处理时间，甚至可能导致程序或系统不稳定。\n\n（基于文件数量 {file_count} 的建议尺寸约为 {recommended_width_approx}x{recommended_height_approx}）\n\n确定要继续创建这个超大图像吗？")
                proceed_large = messagebox.askyesno("确认创建超大图像", warn_message, icon='warning')
            if not proceed_large: self.update_status("操作已取消（因图像尺寸过大）。"); return
        except Exception as size_calc_e: messagebox.showerror("错误", f"计算最终图像尺寸时出错:\n{size_calc_e}"); return

        try: self.status_text.config(state='normal'); self.status_text.delete('1.0', tk.END); self.status_text.config(state='disabled'); self._toggle_controls(False)
        except Exception as ui_e: print(f"警告：准备启动线程时更新UI出错: {ui_e}")

        thread = threading.Thread(target=self.run_sprite_sheet_task, args=(in_dir, current_cols, current_rows, out_path, frame_width, frame_height, image_mode, sorted_image_files, should_resize_output), daemon=True); thread.start()

    # --- run_sprite_sheet_task (简化日志记录) ---
    def run_sprite_sheet_task(self, in_dir, cols, rows, out_path,
                              frame_width, frame_height, image_mode, sorted_image_files,
                              resize_output):
        try:
            success = create_sprite_sheet(in_dir, cols, rows, out_path, self.update_status,
                                          frame_width, frame_height, image_mode, sorted_image_files,
                                          resize_output)
            self.master.after(0, self.on_processing_complete, success)
        except Exception as e:
            # 线程中的错误仍然重要，保留基本信息和可选日志
            print(f"!!! 在 run_sprite_sheet_task 线程中发生严重错误: {e}") # 打印到控制台
            self.update_status(f"后台处理线程出错: {e}") # 更新状态栏
            # 尝试记录日志 (简化版)
            try:
                with open("thread_error.log", "w", encoding='utf-8') as f:
                    f.write(f"后台线程错误:\n{traceback.format_exc()}")
                self.update_status("详细错误信息已记录到 thread_error.log")
            except Exception as log_e:
                self.update_status(f"写入线程错误日志失败: {log_e}")
            # 必须调用 on_processing_complete 来恢复UI
            self.master.after(0, self.on_processing_complete, False)

    # --- on_processing_complete (清理版) ---
    def on_processing_complete(self, success):
        self._toggle_controls(True)
        if success:
            messagebox.showinfo("完成", "序列图处理完成！")
        else:
            messagebox.showerror("失败", "创建序列图时遇到错误，请查看状态信息或日志文件获取详情。")

# --- 程序入口 (清理版) ---
if __name__ == "__main__":
    if not PIL_AVAILABLE:
        try: err_root = tk.Tk(); err_root.withdraw(); messagebox.showerror("依赖错误", "运行此程序需要 Pillow 库。\n请使用 'pip install Pillow' 命令安装。"); err_root.destroy()
        except Exception: pass
        exit("依赖错误：缺少 Pillow 库。")
    root = None
    try:
        root = tk.Tk()
    except Exception as e:
        try:
            with open("root_create_error.log", "w", encoding='utf-8') as f:
                f.write(f"创建 tk.Tk() 失败:\n{traceback.format_exc()}")
        except: pass
        exit("错误：无法创建Tkinter根窗口，程序无法运行。")
    # --- Icon 设置 (注释掉) ---
    # ...
    app = None
    try:
        app = SpriteSheetApp(root)
    except Exception as e:
        try:
            with open("app_init_error.log", "w", encoding='utf-8') as f:
                f.write(f"实例化 SpriteSheetApp 期间出错:\n{traceback.format_exc()}")
            messagebox.showerror("应用程序错误", f"无法初始化应用程序界面:\n{e}\n错误详情已记录到 app_init_error.log")
        except Exception as log_e:
             messagebox.showerror("应用程序错误", f"无法初始化应用程序界面 (日志写入失败):\n{e}")
        try:
            root.destroy()
        except: pass
        exit("错误：应用程序初始化失败，程序退出。")
    if app:
        try:
            root.mainloop()
        except Exception as e:
            try:
                with open("mainloop_error.log", "w", encoding='utf-8') as f:
                    f.write(f"主循环期间出错:\n{traceback.format_exc()}")
            except Exception: pass
    # --- 程序结束 ---