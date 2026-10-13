import ctypes
import json
import os
import random
import shutil
import sys
import uuid
import winreg
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageOps


def resource_path(relative_path):
  try:
    base_path = sys._MEIPASS
  except Exception:
    base_path = os.path.abspath(".")
  return os.path.join(base_path, relative_path)



APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "WallpaperChanger")
IMG_DIR = os.path.join(APP_DIR, "images")
THUMB_DIR = os.path.join(APP_DIR, "thumbs")
DATA_FILE = os.path.join(APP_DIR, "wallpapers.json")
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)

ACCENT = "#3b8ed0"
CARD_W, CARD_H = 224, 126  
COLUMNS = 3


FIT_MODES = {
    "Fill": ("10", "0"),
    "Fit": ("6", "0"),
    "Stretch": ("2", "0"),
    "Center": ("0", "0"),
    "Tile": ("0", "1"),
    "Span (multi-monitor)": ("22", "0"),
}

SPI_SETDESKWALLPAPER = 20
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02


def apply_wallpaper(path, fit_name):
  """Set the display mode and change the desktop wallpaper."""
  style, tile = FIT_MODES.get(fit_name, FIT_MODES["Fill"])
  with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE) as key:
    winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, style)
    winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile)
  ctypes.windll.user32.SystemParametersInfoW(
      SPI_SETDESKWALLPAPER, 0, os.path.abspath(path), SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
  )


def thumb_path(file):
  return os.path.join(THUMB_DIR, file + ".png")


def make_thumb(file):
  """Generate and save a thumbnail once."""
  tp = thumb_path(file)
  if not os.path.exists(tp):
    img = Image.open(os.path.join(IMG_DIR, file)).convert("RGB")
    img = ImageOps.fit(img, (CARD_W * 2, CARD_H * 2))
    img.save(tp, "PNG")
  return tp


def load_ctk_image(file, size):
  img = Image.open(make_thumb(file))
  return ctk.CTkImage(light_image=img, dark_image=img, size=size)


class App(ctk.CTk):

  def __init__(self):
    super().__init__()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    self.title("Wallpaper Changer")
    self.geometry("1060x660")
    self.minsize(900, 560)
    self.resizable(False, False)  

    
    try:
      logo_path = resource_path("logo.ico")
      if not os.path.exists(logo_path):
        logo_path = "logo.ico"
      if os.path.exists(logo_path):
        abs_logo_path = os.path.abspath(logo_path)
        self.iconbitmap(abs_logo_path)
    except Exception:
      pass

    self.items, self.fit = self.load()
    self.selected = None
    self.cards = []
    self.card_images = []

    self.grid_columnconfigure(1, weight=1)
    self.grid_rowconfigure(0, weight=1)
    self.build_sidebar()
    self.build_gallery()
    self.render()

  def load(self):
    items, fit = [], "Fill"
    if os.path.exists(DATA_FILE):
      try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
          data = json.load(f)
        if isinstance(data, list):
          items = data
        else:
          items = data.get("items", [])
          fit = data.get("fit", "Fill")
          # Migrate display-mode names saved by older Turkish versions.
          fit = {
              "Doldur": "Fill",
              "Sığdır": "Fit",
              "Uzat": "Stretch",
              "Ortala": "Center",
              "Döşe": "Tile",
              "Yay (çoklu ekran)": "Span (multi-monitor)",
          }.get(fit, fit)
      except (json.JSONDecodeError, OSError):
        pass
    items = [i for i in items if os.path.exists(os.path.join(IMG_DIR, i["file"]))]
    if fit not in FIT_MODES:
      fit = "Fill"
    return items, fit

  def save(self):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
      json.dump({"items": self.items, "fit": self.fit}, f, ensure_ascii=False, indent=2)

  def build_sidebar(self):
    side = ctk.CTkFrame(self, width=280, corner_radius=0)
    side.grid(row=0, column=0, sticky="nsew")
    side.grid_propagate(False)

    ctk.CTkLabel(side, text="🖼  Wallpaper Changer", font=ctk.CTkFont(size=22, weight="bold")).pack(
        pady=(26, 4), padx=20, anchor="w"
    )
    ctk.CTkLabel(side, text="Change your desktop in one click", text_color="gray60").pack(
        padx=20, anchor="w"
    )

    self.preview = ctk.CTkLabel(
        side,
        text="Select an image",
        width=240,
        height=135,
        corner_radius=12,
        fg_color=("gray80", "gray17"),
        text_color="gray55",
    )
    self.preview.pack(pady=(22, 8), padx=20)

    self.name_label = ctk.CTkLabel(side, text="", wraplength=240, text_color="gray70")
    self.name_label.pack(padx=20)

    ctk.CTkButton(
        side,
        text="✓  Set as Wallpaper",
        height=44,
        font=ctk.CTkFont(size=15, weight="bold"),
        command=self.apply_selected,
    ).pack(pady=(18, 8), padx=20, fill="x")

    ctk.CTkButton(
        side,
        text="🎲  Random",
        height=36,
        fg_color=("gray75", "gray28"),
        hover_color=("gray65", "gray35"),
        command=self.random_wallpaper,
    ).pack(pady=4, padx=20, fill="x")

    ctk.CTkButton(
        side,
        text="＋  Add Images",
        height=36,
        fg_color=("gray75", "gray28"),
        hover_color=("gray65", "gray35"),
        command=self.add_images,
    ).pack(pady=4, padx=20, fill="x")

    ctk.CTkButton(
        side,
        text="🗑  Delete",
        height=36,
        fg_color="#b3402f",
        hover_color="#8f3224",
        command=self.delete_selected,
    ).pack(pady=4, padx=20, fill="x")

    ctk.CTkLabel(side, text="Display Mode", text_color="gray60").pack(pady=(18, 2), padx=20, anchor="w")
    self.fit_menu = ctk.CTkOptionMenu(side, values=list(FIT_MODES.keys()), command=self.on_fit_change)
    self.fit_menu.set(self.fit)
    self.fit_menu.pack(padx=20, fill="x")

    self.status = ctk.CTkLabel(side, text="", text_color="#4cc38a")
    self.status.pack(side="bottom", pady=14)

  def build_gallery(self):
    main = ctk.CTkFrame(self, fg_color="transparent")
    main.grid(row=0, column=1, sticky="nsew", padx=(14, 14), pady=14)
    main.grid_columnconfigure(0, weight=1)
    main.grid_rowconfigure(1, weight=1)

    
    header_frame = ctk.CTkFrame(main, fg_color="transparent")
    header_frame.grid(row=0, column=0, sticky="ew", pady=(4, 10))
    header_frame.grid_columnconfigure(0, weight=1)
    header_frame.grid_columnconfigure(1, weight=1)

    self.header = ctk.CTkLabel(header_frame, text="My Collection", font=ctk.CTkFont(size=20, weight="bold"))
    self.header.grid(row=0, column=0, sticky="w")

    signature_label = ctk.CTkLabel(
        header_frame,
        text="Created by KaramanStudio",
        text_color="gray55",
        font=ctk.CTkFont(size=13),
    )
    signature_label.grid(row=0, column=1, sticky="e", padx=(0, 10))

    self.gallery = ctk.CTkScrollableFrame(main, corner_radius=14)
    self.gallery.grid(row=1, column=0, sticky="nsew")
    for c in range(COLUMNS):
      self.gallery.grid_columnconfigure(c, weight=1)

  def render(self):
    for w in self.gallery.winfo_children():
      w.destroy()
    self.cards.clear()
    self.card_images.clear()

    self.header.configure(text=f"My Collection  ·  {len(self.items)} images")

    if not self.items:
      ctk.CTkLabel(
          self.gallery,
          text="No images yet.\nStart by clicking  ＋ Add Images  on the left.",
          text_color="gray55",
          font=ctk.CTkFont(size=15),
          justify="center",
      ).grid(row=0, column=0, columnspan=COLUMNS, pady=120)
      self.show_preview(None)
      return

    for idx, item in enumerate(self.items):
      card = ctk.CTkFrame(
          self.gallery,
          corner_radius=12,
          border_width=3,
          border_color=("gray80", "gray20"),
          fg_color=("gray85", "gray20"),
      )
      card.grid(row=idx // COLUMNS, column=idx % COLUMNS, padx=8, pady=8)

      img = load_ctk_image(item["file"], (CARD_W, CARD_H))
      self.card_images.append(img)
      pic = ctk.CTkLabel(card, text="", image=img)
      pic.pack(padx=6, pady=(6, 2))

      name = item["name"]
      short = name if len(name) <= 26 else name[:23] + "..."
      txt = ctk.CTkLabel(card, text=short, text_color="gray65", font=ctk.CTkFont(size=12))
      txt.pack(pady=(0, 6))

      for w in (card, pic, txt):
        w.bind("<Button-1>", lambda e, i=idx: self.select(i))
        w.bind("<Double-Button-1>", lambda e, i=idx: self.select_and_apply(i))
        w.bind("<Enter>", lambda e, c=card, i=idx: self.on_card_enter(c, i))
        w.bind("<Leave>", lambda e, c=card, i=idx: self.on_card_leave(c, i))

      self.cards.append(card)

    if self.selected is not None and self.selected < len(self.items):
      self.select(self.selected)
    else:
      self.selected = None
      self.show_preview(None)

  def on_card_enter(self, card, idx):
    if self.selected != idx:
      card.configure(border_color="#6baed6")

  def on_card_leave(self, card, idx):
    if self.selected != idx:
      card.configure(border_color=("gray80", "gray20"))

  def select(self, idx):
    self.selected = idx
    for i, card in enumerate(self.cards):
      card.configure(border_color=ACCENT if i == idx else ("gray80", "gray20"))
    self.show_preview(self.items[idx])

  def show_preview(self, item):
    if item is None:
      self.preview.configure(image=None, text="Select an image")
      self.name_label.configure(text="")
      return
    self.preview_img = load_ctk_image(item["file"], (240, 135))
    self.preview.configure(image=self.preview_img, text="")
    self.name_label.configure(text=item["name"])

  def flash(self, text, color="#4cc38a"):
    self.status.configure(text=text, text_color=color)
    self.after(2500, lambda: self.status.configure(text=""))

  def add_images(self):
    paths = filedialog.askopenfilenames(
        title="Select images", filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")]
    )
    added = 0
    for p in paths:
      try:
        ext = os.path.splitext(p)[1].lower()
        new_file = f"{uuid.uuid4().hex}{ext}"
        shutil.copy(p, os.path.join(IMG_DIR, new_file))
        make_thumb(new_file)
        self.items.append({"name": os.path.basename(p), "file": new_file})
        added += 1
      except Exception as e:
        messagebox.showerror("Error", f"Could not add {os.path.basename(p)}:\n{e}")
    if added:
      self.save()
      self.selected = len(self.items) - 1
      self.render()
      self.flash(f"✓ Added {added} image(s)")

  def apply_selected(self):
    if self.selected is None:
      self.flash("Select an image first", "#e0a030")
      return
    item = self.items[self.selected]
    apply_wallpaper(os.path.join(IMG_DIR, item["file"]), self.fit)
    self.flash("✓ Wallpaper changed")

  def select_and_apply(self, idx):
    self.select(idx)
    self.apply_selected()

  def random_wallpaper(self):
    if not self.items:
      self.flash("Add an image first", "#e0a030")
      return
    choices = [i for i in range(len(self.items)) if i != self.selected] or [0]
    self.select(random.choice(choices))
    self.apply_selected()

  def delete_selected(self):
    if self.selected is None:
      self.flash("Select an image first", "#e0a030")
      return
    item = self.items[self.selected]
    if messagebox.askyesno("Delete", f"Remove '{item['name']}' from your collection?"):
      for path in (os.path.join(IMG_DIR, item["file"]), thumb_path(item["file"])):
        try:
          os.remove(path)
        except OSError:
          pass
      self.items.pop(self.selected)
      self.selected = None
      self.save()
      self.render()
      self.flash("✓ Deleted")

  def on_fit_change(self, value):
    self.fit = value
    self.save()


if __name__ == "__main__":
  App().mainloop()