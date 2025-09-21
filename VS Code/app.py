#!/usr/bin/env python3
import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
import json
import socket
import os
import random

PLAYERS_FILE = "players.json"
ESP_PORT = 5000  # по умолчанию


class Player:
    def __init__(self, name="", klass="", hp=0, cd=0):
        self.name = name
        self.klass = klass
        self.hp = hp
        self.cd = cd
        self.init = 0

    def to_dict(self):
        return {"name": self.name, "class": self.klass,
                "hp": self.hp, "cd": self.cd, "init": self.init}


class Enemy:
    def __init__(self, name="", hp=0, cd=0):
        self.name = name
        self.hp = hp
        self.cd = cd
        self.init = 0

    def to_dict(self):
        return {"name": self.name, "class": "Enemy",
                "hp": self.hp, "cd": self.cd, "init": self.init}


class App:
    def __init__(self, root):
        self.root = root
        root.title("DnD Host - Initiative")
        self.players = []
        self.enemies = []
        self.battle_units = []   # игроки + враги в бою
        self.current_index = None
        self.in_battle = False

        self.esp_ip = tk.StringVar(value="")
        self.esp_port = tk.IntVar(value=ESP_PORT)

        frm = ttk.Frame(root, padding=8)
        frm.grid(row=0, column=0, sticky="nsew")

        # Connection
        conn_frame = ttk.LabelFrame(frm, text="ESP Connection")
        conn_frame.grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Label(conn_frame, text="ESP IP:").grid(row=0, column=0)
        ttk.Entry(conn_frame, textvariable=self.esp_ip, width=18).grid(row=0, column=1)
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2)
        ttk.Entry(conn_frame, textvariable=self.esp_port, width=6).grid(row=0, column=3)
        ttk.Button(conn_frame, text="Test Connect", command=self.test_connect).grid(row=0, column=4, padx=6)

        # Players list
        players_frame = ttk.LabelFrame(frm, text="Players")
        players_frame.grid(row=1, column=0, sticky="nsew", pady=4)
        self.lb = tk.Listbox(players_frame, width=50, height=12)
        self.lb.grid(row=0, column=0, rowspan=4, padx=6, pady=6)
        ttk.Button(players_frame, text="Add", command=self.add_player).grid(row=0, column=1, sticky="ew")
        ttk.Button(players_frame, text="Edit", command=self.edit_player).grid(row=1, column=1, sticky="ew")
        ttk.Button(players_frame, text="Delete", command=self.del_player).grid(row=2, column=1, sticky="ew")
        ttk.Button(players_frame, text="Save", command=self.save_players).grid(row=3, column=1, sticky="ew")

        # Actions
        actions = ttk.LabelFrame(frm, text="Actions")
        actions.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(actions, text="Start Battle", command=self.start_battle).grid(row=0, column=0, padx=4)
        ttk.Button(actions, text="Stop Battle", command=self.stop_battle).grid(row=0, column=1, padx=4)
        ttk.Button(actions, text="Next Turn", command=self.next_turn).grid(row=0, column=2, padx=4)
        ttk.Button(actions, text="Set Current", command=self.set_current).grid(row=0, column=3, padx=4)

        # load existing
        self.load_players()
        self.refresh_list()

    # ---------------- Networking ----------------
    def send_json(self, obj):
        ip = self.esp_ip.get().strip()
        port = int(self.esp_port.get())
        if not ip:
            messagebox.showwarning("No IP", "Enter ESP IP first")
            return False
        try:
            with socket.create_connection((ip, port), timeout=3) as s:
                data = json.dumps(obj) + "\n"
                s.sendall(data.encode("utf-8"))
            return True
        except Exception as e:
            messagebox.showerror("Send error", f"Failed to send: {e}")
            return False

    def test_connect(self):
        ip = self.esp_ip.get().strip()
        port = int(self.esp_port.get())
        if not ip:
            messagebox.showwarning("No IP", "Enter ESP IP first")
            return
        try:
            with socket.create_connection((ip, port), timeout=3) as s:
                messagebox.showinfo("OK", "Connected to ESP (accepted).")
        except Exception as e:
            messagebox.showerror("Failed", f"Cannot connect: {e}")

    # ---------------- Players ----------------
    def load_players(self):
        if os.path.exists(PLAYERS_FILE):
            with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
                arr = json.load(f)
            self.players = [Player(p.get("name", ""), p.get("class", ""),
                                   p.get("hp", 0), p.get("cd", 0)) for p in arr]
        else:
            self.players = []

    def save_players(self):
        arr = [p.to_dict() for p in self.players]
        with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
            json.dump(arr, f, indent=2)
        messagebox.showinfo("Saved", "Players saved to players.json")

    def refresh_list(self):
        """Обновляем список в UI"""
        self.lb.delete(0, tk.END)
        units = self.battle_units if self.in_battle else self.players
        for i, u in enumerate(units):
            text = f"{i+1}. {u.name} ({getattr(u, 'klass', 'Enemy')}) HP:{u.hp} CD:{u.cd} Init:{u.init}"
            self.lb.insert(tk.END, text)

        if self.in_battle and self.current_index is not None:
            self.lb.selection_clear(0, tk.END)
            self.lb.selection_set(self.current_index)
            self.lb.activate(self.current_index)

    def add_player(self):
        dlg = PlayerDialog(self.root)
        self.root.wait_window(dlg.top)
        if dlg.result:
            p = Player(dlg.result["name"], dlg.result["class"],
                       int(dlg.result["hp"]), int(dlg.result["cd"]))
            self.players.append(p)
            self.refresh_list()

    def edit_player(self):
        sel = self.lb.curselection()
        if not sel:
            return
        idx = sel[0]
        units = self.battle_units if self.in_battle else self.players
        p = units[idx]
        dlg = PlayerDialog(self.root, p)
        self.root.wait_window(dlg.top)
        if dlg.result:
            p.name = dlg.result["name"]
            if isinstance(p, Player):
                p.klass = dlg.result["class"]
            p.hp = int(dlg.result["hp"])
            p.cd = int(dlg.result["cd"])
            self.refresh_list()

    def del_player(self):
        sel = self.lb.curselection()
        if not sel:
            return
        idx = sel[0]
        del self.players[idx]
        self.refresh_list()

    # ---------------- Battle ----------------
    def start_battle(self):
        if not self.players:
            messagebox.showwarning("No players", "Add players before starting battle")
            return

        # окно врагов
        enemy_win = EnemyManager(self.root, self.enemies)
        self.root.wait_window(enemy_win.top)
        if enemy_win.result is None:
            return
        self.enemies = enemy_win.result

        # инициативы игроков
        used_inits = set()
        for p in self.players:
            val = simpledialog.askinteger(
                "Initiative",
                f"Введите инициативу для {p.name} ({p.klass})",
                parent=self.root, minvalue=1, maxvalue=20
            )
            if val is not None:
                while val in used_inits:
                    messagebox.showwarning("Duplicate", f"Инициатива {val} уже занята, выберите другую")
                    val = simpledialog.askinteger(
                        "Initiative",
                        f"Введите инициативу для {p.name} ({p.klass})",
                        parent=self.root, minvalue=1, maxvalue=20
                    )
                p.init = val
                used_inits.add(val)

        # инициативы врагов автоматически
        all_possible = list(set(range(1, 21)) - used_inits)
        random.shuffle(all_possible)
        for i, e in enumerate(self.enemies):
            e.init = all_possible[i] if i < len(all_possible) else 0

        # список всех участников
        self.battle_units = self.players + self.enemies
        # сортировка по инициативе
        self.battle_units.sort(key=lambda u: u.init, reverse=True)
        self.in_battle = True
        self.current_index = 0

        arr = [u.to_dict() for u in self.battle_units]
        ok1 = self.send_json({"cmd": "init_players", "players": arr})
        ok2 = self.send_json({"cmd": "start_battle"})
        if ok1 and ok2:
            messagebox.showinfo("Started", "Battle started on ESP")

        self.refresh_list()

    def stop_battle(self):
        for p in self.players:
            p.init = 0
        self.enemies = []
        self.battle_units = []
        self.current_index = None
        self.in_battle = False
        ok = self.send_json({"cmd": "stop_battle"})
        if ok:
            messagebox.showinfo("Stopped", "Battle stopped on ESP")
        self.refresh_list()

    def next_turn(self):
        if not self.in_battle or not self.battle_units:
            return
        self.current_index = (self.current_index + 1) % len(self.battle_units)
        ok = self.send_json({"cmd": "next_turn"})
        if ok:
            self.refresh_list()

    def set_current(self):
        sel = self.lb.curselection()
        if not sel:
            messagebox.showwarning("Select", "Select unit in list")
            return
        self.current_index = sel[0]
        ok = self.send_json({"cmd": "set_current", "index": self.current_index})
        if ok:
            self.refresh_list()


# ---------------- Dialogs ----------------
class PlayerDialog:
    def __init__(self, parent, player=None):
        top = self.top = tk.Toplevel(parent)
        top.title("Player")
        self.result = None

        ttk.Label(top, text="Name").grid(row=0, column=0)
        self.e_name = ttk.Entry(top)
        self.e_name.grid(row=0, column=1)
        ttk.Label(top, text="Class").grid(row=1, column=0)
        self.e_class = ttk.Entry(top)
        self.e_class.grid(row=1, column=1)
        ttk.Label(top, text="HP").grid(row=2, column=0)
        self.e_hp = ttk.Entry(top)
        self.e_hp.grid(row=2, column=1)
        ttk.Label(top, text="CD").grid(row=3, column=0)
        self.e_cd = ttk.Entry(top)
        self.e_cd.grid(row=3, column=1)

        if player:
            self.e_name.insert(0, player.name)
            if hasattr(player, "klass"):
                self.e_class.insert(0, player.klass)
            self.e_hp.insert(0, str(player.hp))
            self.e_cd.insert(0, str(player.cd))

        ttk.Button(top, text="OK", command=self.ok).grid(row=5, column=0)
        ttk.Button(top, text="Cancel", command=self.cancel).grid(row=5, column=1)

    def ok(self):
        self.result = {
            "name": self.e_name.get().strip(),
            "class": self.e_class.get().strip(),
            "hp": int(self.e_hp.get() or 0),
            "cd": int(self.e_cd.get() or 0)
        }
        self.top.destroy()

    def cancel(self):
        self.top.destroy()


class EnemyDialog:
    def __init__(self, parent, enemy=None):
        top = self.top = tk.Toplevel(parent)
        top.title("Enemy")
        self.result = None

        ttk.Label(top, text="Name").grid(row=0, column=0)
        self.e_name = ttk.Entry(top)
        self.e_name.grid(row=0, column=1)
        ttk.Label(top, text="HP").grid(row=1, column=0)
        self.e_hp = ttk.Entry(top)
        self.e_hp.grid(row=1, column=1)
        ttk.Label(top, text="CD").grid(row=2, column=0)
        self.e_cd = ttk.Entry(top)
        self.e_cd.grid(row=2, column=1)

        if enemy:
            self.e_name.insert(0, enemy.name)
            self.e_hp.insert(0, str(enemy.hp))
            self.e_cd.insert(0, str(enemy.cd))

        ttk.Button(top, text="OK", command=self.ok).grid(row=3, column=0)
        ttk.Button(top, text="Cancel", command=self.cancel).grid(row=3, column=1)

    def ok(self):
        self.result = {
            "name": self.e_name.get().strip(),
            "hp": int(self.e_hp.get() or 0),
            "cd": int(self.e_cd.get() or 0)
        }
        self.top.destroy()

    def cancel(self):
        self.top.destroy()


class EnemyManager:
    def __init__(self, parent, enemies):
        top = self.top = tk.Toplevel(parent)
        top.title("Enemies")
        self.result = None
        self.enemies = enemies.copy()

        frm = ttk.Frame(top, padding=6)
        frm.grid(row=0, column=0)

        self.lb = tk.Listbox(frm, width=40, height=8)
        self.lb.grid(row=0, column=0, rowspan=4, padx=4, pady=4)
        ttk.Button(frm, text="Add", command=self.add_enemy).grid(row=0, column=1)
        ttk.Button(frm, text="Edit", command=self.edit_enemy).grid(row=1, column=1)
        ttk.Button(frm, text="Delete", command=self.del_enemy).grid(row=2, column=1)
        ttk.Button(frm, text="Submit", command=self.submit).grid(row=3, column=1)

        self.refresh()

    def refresh(self):
        self.lb.delete(0, tk.END)
        for e in self.enemies:
            self.lb.insert(tk.END, f"{e.name} (HP:{e.hp} CD:{e.cd})")

    def add_enemy(self):
        dlg = EnemyDialog(self.top)
        self.top.wait_window(dlg.top)
        if dlg.result:
            e = Enemy(dlg.result["name"], dlg.result["hp"], dlg.result["cd"])
            self.enemies.append(e)
            self.refresh()

    def edit_enemy(self):
        sel = self.lb.curselection()
        if not sel:
            return
        idx = sel[0]
        e = self.enemies[idx]
        dlg = EnemyDialog(self.top, e)
        self.top.wait_window(dlg.top)
        if dlg.result:
            e.name = dlg.result["name"]
            e.hp = dlg.result["hp"]
            e.cd = dlg.result["cd"]
            self.refresh()

    def del_enemy(self):
        sel = self.lb.curselection()
        if not sel:
            return
        idx = sel[0]
        del self.enemies[idx]
        self.refresh()

    def submit(self):
        self.result = self.enemies
        self.top.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
