#!/usr/bin/env python3
import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
import json
import socket
import os

PLAYERS_FILE = "players.json"
ESP_PORT = 5000  # по умолчанию

class Player:
    def __init__(self, name="", klass="", hp=0, cd=0, init=0):
        self.name = name
        self.klass = klass
        self.hp = hp
        self.cd = cd
        self.init = init
    def to_dict(self):
        return {"name": self.name, "class": self.klass, "hp": self.hp, "cd": self.cd, "init": self.init}

class App:
    def __init__(self, root):
        self.root = root
        root.title("DnD Host - Initiative (simple)")
        self.players = []
        self.esp_ip = tk.StringVar(value="")  # впиши IP ESP
        self.esp_port = tk.IntVar(value=ESP_PORT)
        self.sock = None

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
        self.lb = tk.Listbox(players_frame, width=50, height=10)
        self.lb.grid(row=0, column=0, rowspan=4, padx=6, pady=6)
        btn_add = ttk.Button(players_frame, text="Add", command=self.add_player)
        btn_add.grid(row=0, column=1, sticky="ew")
        btn_edit = ttk.Button(players_frame, text="Edit", command=self.edit_player)
        btn_edit.grid(row=1, column=1, sticky="ew")
        btn_del = ttk.Button(players_frame, text="Delete", command=self.del_player)
        btn_del.grid(row=2, column=1, sticky="ew")
        btn_save = ttk.Button(players_frame, text="Save", command=self.save_players)
        btn_save.grid(row=3, column=1, sticky="ew")

        # Actions
        actions = ttk.LabelFrame(frm, text="Actions")
        actions.grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(actions, text="Send Players", command=self.send_players).grid(row=0, column=0, padx=4)
        ttk.Button(actions, text="Start Battle", command=self.start_battle).grid(row=0, column=1, padx=4)
        ttk.Button(actions, text="Stop Battle", command=self.stop_battle).grid(row=0, column=2, padx=4)
        ttk.Button(actions, text="Next Turn", command=self.next_turn).grid(row=0, column=3, padx=4)
        ttk.Button(actions, text="Set Current", command=self.set_current).grid(row=0, column=4, padx=4)

        # load existing
        self.load_players()
        self.refresh_list()

    # networking
    def send_json(self, obj):
        ip = self.esp_ip.get().strip()
        port = int(self.esp_port.get())
        if not ip:
            messagebox.showwarning("No IP", "Enter ESP IP first")
            return False
        try:
            with socket.create_connection((ip, port), timeout=3) as s:
                # send JSON + newline
                data = json.dumps(obj) + "\n"
                s.sendall(data.encode('utf-8'))
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

    # player ops
    def load_players(self):
        if os.path.exists(PLAYERS_FILE):
            with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
                arr = json.load(f)
            self.players = [Player(p.get("name",""), p.get("class",""), p.get("hp",0), p.get("cd",0), p.get("init",0)) for p in arr]
        else:
            self.players = []

    def save_players(self):
        arr = [p.to_dict() for p in self.players]
        with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
            json.dump(arr, f, indent=2)
        messagebox.showinfo("Saved", "Players saved to players.json")

    def refresh_list(self):
        self.lb.delete(0, tk.END)
        for i,p in enumerate(self.players):
            self.lb.insert(tk.END, f"{i+1}. {p.name} ({p.klass}) HP:{p.hp} CD:{p.cd} Init:{p.init}")

    def add_player(self):
        dlg = PlayerDialog(self.root)
        self.root.wait_window(dlg.top)
        if dlg.result:
            p = Player(dlg.result['name'], dlg.result['class'], int(dlg.result['hp']), int(dlg.result['cd']), int(dlg.result['init']))
            self.players.append(p)
            self.refresh_list()

    def edit_player(self):
        sel = self.lb.curselection()
        if not sel: return
        idx = sel[0]
        p = self.players[idx]
        dlg = PlayerDialog(self.root, p)
        self.root.wait_window(dlg.top)
        if dlg.result:
            p.name = dlg.result['name']
            p.klass = dlg.result['class']
            p.hp = int(dlg.result['hp'])
            p.cd = int(dlg.result['cd'])
            p.init = int(dlg.result['init'])
            self.refresh_list()

    def del_player(self):
        sel = self.lb.curselection()
        if not sel: return
        idx = sel[0]
        del self.players[idx]
        self.refresh_list()

    # commands
    def send_players(self):
        arr = [p.to_dict() for p in self.players]
        msg = {"cmd":"init_players", "players": arr}
        ok = self.send_json(msg)
        if ok: messagebox.showinfo("Sent", "Players sent to ESP")

    def start_battle(self):
        if not self.players:
            messagebox.showwarning("No players", "Add players before starting battle")
            return

        # спросить инициативу у каждого игрока
        for p in self.players:
            try:
                val = simpledialog.askinteger("Initiative", f"Введите инициативу для {p.name} ({p.klass})", parent=self.root, minvalue=0, maxvalue=50)
                if val is not None:
                    p.init = val
            except Exception:
                pass

        self.refresh_list()

        # сортировка по инициативе
        order = sorted(list(range(len(self.players))), key=lambda i: self.players[i].init, reverse=True)
        msg = {"cmd":"start_battle", "order": order}
        ok = self.send_json(msg)
        if ok: messagebox.showinfo("Started", "Battle started on ESP")

    def stop_battle(self):
        for p in self.players:
            p.init = 0
        self.refresh_list()
        msg = {"cmd":"stop_battle"}
        ok = self.send_json(msg)
        if ok: messagebox.showinfo("Stopped", "Battle stopped on ESP (initiative reset)")


    def next_turn(self):
        msg = {"cmd":"next_turn"}
        ok = self.send_json(msg)
        if ok: messagebox.showinfo("Sent", "Next turn command sent")

    def set_current(self):
        sel = self.lb.curselection()
        if not sel:
            messagebox.showwarning("Select", "Select player in list")
            return
        idx = sel[0]
        msg = {"cmd":"set_current", "index": idx}
        ok = self.send_json(msg)
        if ok: messagebox.showinfo("Sent", f"Set current to {idx+1}")

class PlayerDialog:
    def __init__(self, parent, player=None):
        top = self.top = tk.Toplevel(parent)
        top.title("Player")
        self.result = None

        ttk.Label(top, text="Name").grid(row=0,column=0)
        self.e_name = ttk.Entry(top); self.e_name.grid(row=0,column=1)
        ttk.Label(top, text="Class").grid(row=1,column=0)
        self.e_class = ttk.Entry(top); self.e_class.grid(row=1,column=1)
        ttk.Label(top, text="HP").grid(row=2,column=0)
        self.e_hp = ttk.Entry(top); self.e_hp.grid(row=2,column=1)
        ttk.Label(top, text="CD").grid(row=3,column=0)
        self.e_cd = ttk.Entry(top); self.e_cd.grid(row=3,column=1)
        ttk.Label(top, text="Init").grid(row=4,column=0)
        self.e_init = ttk.Entry(top); self.e_init.grid(row=4,column=1)

        if player:
            self.e_name.insert(0, player.name)
            self.e_class.insert(0, player.klass)
            self.e_hp.insert(0, str(player.hp))
            self.e_cd.insert(0, str(player.cd))
            self.e_init.insert(0, str(player.init))

        ttk.Button(top, text="OK", command=self.ok).grid(row=5,column=0)
        ttk.Button(top, text="Cancel", command=self.cancel).grid(row=5,column=1)

    def ok(self):
        self.result = {
            "name": self.e_name.get().strip(),
            "class": self.e_class.get().strip(),
            "hp": int(self.e_hp.get() or 0),
            "cd": int(self.e_cd.get() or 0),
            "init": int(self.e_init.get() or 0)
        }
        self.top.destroy()

    def cancel(self):
        self.top.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    from tkinter import ttk
    app = App(root)
    root.mainloop()
