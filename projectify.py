import tkinter as tk
from tkinter import ttk, messagebox
import math
import matplotlib.pyplot as plt
import sqlite3
import numpy as np
import json
import hashlib
from abc import ABC, abstractmethod

GRAVITY = 9.8
DT = 0.1
SCALE = 5
GROUND_Y = 400

def clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))

class DatabaseManager:
    def __init__(self, db_file="simulation_data.db"):
        self.conn = sqlite3.connect(db_file)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT,
                email TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                topic TEXT,
                parameters TEXT,
                results TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
        """)
        self.conn.commit()

    def register_user(self, username, password, email=""):
        try:
            cursor = self.conn.cursor()
            pw_hash = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, pw_hash, email)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def login_user(self, username, password):
        cursor = self.conn.cursor()
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute(
            "SELECT id FROM users WHERE username=? AND password_hash=?",
            (username, pw_hash)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def save(self, user_id, topic, params, results):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO simulation_results (user_id, topic, parameters, results)
                VALUES (?, ?, ?, ?)
            """, (user_id, topic, json.dumps(params), json.dumps(results)))
            self.conn.commit()
        except sqlite3.Error:
            pass

    def load_all(self, user_id=None, topic=None):
        cursor = self.conn.cursor()
        if user_id and topic:
            cursor.execute("SELECT * FROM simulation_results WHERE user_id=? AND topic=?", (user_id, topic))
        elif user_id:
            cursor.execute("SELECT * FROM simulation_results WHERE user_id=?", (user_id,))
        elif topic:
            cursor.execute("SELECT * FROM simulation_results WHERE topic=?", (topic,))
        else:
            cursor.execute("SELECT * FROM simulation_results")
        return cursor.fetchall()

class LoginScreen:
    def __init__(self, root, db_manager):
        self.root = root
        self.db = db_manager
        self.user_id = None
        self.build_ui()

    def build_ui(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.title("ProjectiFy - Login")
        self.root.configure(bg="black")
        tk.Label(self.root, text="ProjectiFy Login", font=("Helvetica", 20, "bold"), fg="white", bg="black").pack(pady=20)
        tk.Label(self.root, text="Username:", fg="white", bg="black").pack()
        self.username_entry = ttk.Entry(self.root)
        self.username_entry.pack()
        tk.Label(self.root, text="Password:", fg="white", bg="black").pack()
        self.password_entry = ttk.Entry(self.root, show="*")
        self.password_entry.pack()
        ttk.Button(self.root, text="Login", command=self.login).pack(pady=5)
        ttk.Button(self.root, text="Register", command=self.register).pack(pady=5)

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        user_id = self.db.login_user(username, password)
        if user_id:
            self.user_id = user_id
            ProfileScreen(self.root, self.db, user_id, username)
        else:
            messagebox.showerror("Error", "Invalid username or password")

    def register(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        if self.db.register_user(username, password):
            messagebox.showinfo("Success", "User registered successfully")
        else:
            messagebox.showerror("Error", "Username already exists")

class ProfileScreen:
    def __init__(self, root, db_manager, user_id, username):
        self.root, self.db = root, db_manager
        self.user_id, self.username = user_id, username
        self.build_ui()

    def build_ui(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.title("ProjectiFy - Profile")
        self.root.configure(bg="black")
        tk.Label(self.root, text=f"Welcome, {self.username}!", font=("Helvetica", 20, "bold"), fg="white", bg="black").pack(pady=20)
        ttk.Button(self.root, text="Start Simulations", command=self.start_simulations).pack(pady=10)
        ttk.Button(self.root, text="View My Simulations", command=self.view_my_sims).pack(pady=10)
        ttk.Button(self.root, text="Logout", command=self.logout).pack(pady=10)

    def start_simulations(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        SimulationApp(self.root, self.user_id, self.db, self.username)

    def view_my_sims(self):
        sims = self.db.load_all(self.user_id)
        win = tk.Toplevel(self.root)
        win.title("My Simulations")
        text = tk.Text(win, wrap="word", width=100, height=30, bg="black", fg="white")
        text.pack(padx=10, pady=10)
        for r in sims:
            text.insert("end", f"Topic: {r[2]}, Params: {r[3]}, Results: {r[4]}, Date: {r[5]}\n\n")

    def logout(self):
        LoginScreen(self.root, self.db)

class Simulation(ABC):
    def __init__(self, root, canvas, db_manager, user_id):
        self.root, self.canvas, self.db, self.user_id = root, canvas, db_manager, user_id
        self.running = False
        self.paused = False

    @abstractmethod
    def reset_simulation(self): pass

    @abstractmethod
    def simulate_step(self): pass

    @abstractmethod
    def save_results(self): pass

    @abstractmethod
    def draw(self): pass

    def stop(self):
        if self.running:
            try:
                self.save_results()
            except Exception:
                pass
        self.running = False
        self.paused = False

class ProjectileSim(Simulation):
    def __init__(self, root, canvas, db_manager, param_frame, user_id):
        super().__init__(root, canvas, db_manager, user_id)
        self.param_frame = param_frame
        self.trajectory, self.velocities, self.times = [], [], []
        self.pos_x = self.pos_y = self.vx = self.vy = 0
        self.max_height, self.range_x, self.time_elapsed = 0, 0, 0
        self.create_ui()

    def create_ui(self):
        for widget in self.param_frame.winfo_children(): widget.destroy()
        self.speed_entry = self.create_labeled_entry("Initial Speed (u):", "50")
        self.angle_entry = self.create_labeled_entry("Angle (θ):", "45")
        self.mass_entry = self.create_labeled_entry("Mass (kg):", "1.0")
        self.air_entry = self.create_labeled_entry("Air Resistance:", "0.01")
        ttk.Button(self.param_frame, text="Start / Reset", command=self.reset_simulation).grid(row=5, column=0)
        ttk.Button(self.param_frame, text="Pause / Resume", command=self.pause_resume).grid(row=5, column=1)
        ttk.Button(self.param_frame, text="Step", command=self.step_once).grid(row=5, column=2)
        ttk.Button(self.param_frame, text="Show Graphs", command=self.plot_graphs).grid(row=5, column=3)
        ttk.Button(self.param_frame, text="Stop", command=self.stop).grid(row=5, column=5)
        self.info_text = tk.StringVar()
        tk.Label(self.param_frame, textvariable=self.info_text, fg="white", bg="black", justify="left", font=("Courier", 10)).grid(row=6, column=0, columnspan=6)

    def create_labeled_entry(self, label, default=""):
        row = len(self.param_frame.winfo_children()) // 2
        tk.Label(self.param_frame, text=label, fg="white", bg="black").grid(row=row, column=0, sticky="e")
        entry = ttk.Entry(self.param_frame)
        entry.insert(0, default)
        entry.grid(row=row, column=1, sticky="w")
        return entry

    def reset_simulation(self):
        try:
            self.canvas.delete("all"); self.trajectory.clear(); self.velocities.clear(); self.times.clear()
            if float(self.speed_entry.get()) > 90:
                messagebox.showwarning("Input limited", "Speed capped at 90 m/s for stability.")
                self.running = False; return
            u = clamp(float(self.speed_entry.get()), 0, 200)
            angle_rad = math.radians(clamp(float(self.angle_entry.get()), 0, 90))
            self.mass = clamp(float(self.mass_entry.get()), 0.1, 50)
            self.air_resistance = clamp(float(self.air_entry.get()), 0, 1)
            self.vx, self.vy = u * math.cos(angle_rad), u * math.sin(angle_rad)
            self.pos_x, self.pos_y = 50, GROUND_Y
            self.running, self.paused, self.time_elapsed = True, False, 0
            self.max_height, self.range_x = GROUND_Y, 0
            self.simulate_step()
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric parameters")

    def simulate_step(self):
        if self.running and not self.paused:
            ax = -self.air_resistance * self.vx / self.mass
            ay = GRAVITY - self.air_resistance * self.vy / self.mass
            self.vx += ax * DT; self.vy += ay * DT
            self.pos_x += self.vx * DT * SCALE; self.pos_y += self.vy * DT * SCALE
            if self.pos_y > GROUND_Y:
                self.pos_y = GROUND_Y; self.vy *= -0.6
            self.max_height = min(self.max_height, self.pos_y)
            self.range_x = self.pos_x - 50
            self.trajectory.append((self.pos_x, self.pos_y))
            self.velocities.append(math.sqrt(self.vx ** 2 + self.vy ** 2))
            self.time_elapsed += DT; self.times.append(self.time_elapsed)
            self.draw()
            self.canvas.xview_moveto(max((self.pos_x - 400) / 3000, 0))
            self.canvas.yview_moveto(max((self.pos_y - 250) / 1000, 0))
            self.update_info()
            self.root.after(30, self.simulate_step)

    def draw(self):
        self.canvas.delete("projectile")
        self.canvas.create_oval(self.pos_x - 5, self.pos_y - 5, self.pos_x + 5, self.pos_y + 5, fill="red", tags="projectile")
        for i in range(1, len(self.trajectory)):
            x1, y1 = self.trajectory[i - 1]; x2, y2 = self.trajectory[i]
            self.canvas.create_line(x1, y1, x2, y2, fill="cyan", width=1)

    def update_info(self):
        self.info_text.set(f"Max Height: {round((GROUND_Y-self.max_height)/SCALE,2)} m   Range: {round(self.range_x/SCALE,2)} m   Time: {round(self.time_elapsed,2)} s")

    def pause_resume(self): self.paused = not self.paused

    def step_once(self):
        self.paused = False; self.simulate_step(); self.paused = True

    def save_results(self):
        params = {"u": float(self.speed_entry.get()), "angle": float(self.angle_entry.get()), "mass": float(self.mass_entry.get()), "air": float(self.air_entry.get())}
        results = {"max_height": round((GROUND_Y-self.max_height)/SCALE,4), "range": round(self.range_x/SCALE,4), "time": round(self.time_elapsed,4)}
        if self.user_id: self.db.save(self.user_id, "Projectile Motion", params, results)

    def plot_graphs(self):
        if not self.times:
            messagebox.showinfo("No data", "Run a simulation first."); return
        disp = [GROUND_Y-y for _,y in self.trajectory]
        plt.figure(figsize=(10,4))
        plt.subplot(1,2,1); plt.plot(self.times,disp); plt.xlabel("Time (s)"); plt.ylabel("Vertical Displacement"); plt.title("Displacement vs Time"); plt.grid()
        plt.subplot(1,2,2); plt.plot(self.times,self.velocities); plt.xlabel("Time (s)"); plt.ylabel("Velocity"); plt.title("Velocity vs Time"); plt.grid()
        plt.tight_layout(); plt.show()

class PendulumSim(Simulation):
    def __init__(self, root, canvas, db_manager, param_frame, user_id):
        super().__init__(root, canvas, db_manager, user_id)
        self.param_frame=param_frame; self.angles=[]; self.angular_velocities=[]; self.times=[]
        self.theta=self.omega=0; self.length=1.0; self.damping=0.01; self.time_elapsed=0
        self.create_ui()

    def create_ui(self):
        for w in self.param_frame.winfo_children(): w.destroy()
        self.length_entry=self.create_labeled_entry("Pendulum Length (m):","1.0")
        self.angle_entry=self.create_labeled_entry("Initial Angle (deg):","45")
        self.damping_entry=self.create_labeled_entry("Damping Coefficient:","0.01")
        ttk.Button(self.param_frame,text="Start / Reset",command=self.reset_simulation).grid(row=5,column=0)
        ttk.Button(self.param_frame,text="Pause",command=self.pause_resume).grid(row=5,column=1)
        ttk.Button(self.param_frame,text="Step",command=self.step_once).grid(row=5,column=2)
        ttk.Button(self.param_frame,text="Show Graphs",command=self.plot_graphs).grid(row=5,column=3)
        ttk.Button(self.param_frame,text="Stop",command=self.stop).grid(row=5,column=5)
        self.info_text=tk.StringVar()
        tk.Label(self.param_frame,textvariable=self.info_text,fg="white",bg="black",justify="left",font=("Courier",10)).grid(row=6,column=0,columnspan=6)

    def create_labeled_entry(self,label,default=""):
        row=len(self.param_frame.winfo_children())//2
        tk.Label(self.param_frame,text=label,fg="white",bg="black").grid(row=row,column=0,sticky="e")
        entry=ttk.Entry(self.param_frame); entry.insert(0,default); entry.grid(row=row,column=1,sticky="w"); return entry

    def reset_simulation(self):
        try:
            self.canvas.delete("all"); self.angles.clear(); self.angular_velocities.clear(); self.times.clear()
            if float(self.length_entry.get())>150:
                messagebox.showwarning("Input limited","Length capped at 150m for stability."); self.running=False; return
            if float(self.damping_entry.get())>10:
                messagebox.showwarning("Input limited","Damping capped at 10 for stability."); self.running=False; return
            self.length=float(self.length_entry.get()); self.theta=math.radians(float(self.angle_entry.get()))
            self.damping=float(self.damping_entry.get()); self.omega=0; self.time_elapsed=0
            self.running=True; self.paused=False; self.simulate_step()
        except ValueError: messagebox.showerror("Error","Please enter valid numeric parameters")

    def simulate_step(self):
        if self.running and not self.paused:
            alpha=-(GRAVITY/self.length)*math.sin(self.theta)-self.damping*self.omega
            self.omega+=alpha*DT; self.theta+=self.omega*DT; self.time_elapsed+=DT
            self.angles.append(self.theta); self.angular_velocities.append(self.omega); self.times.append(self.time_elapsed)
            self.draw(); self.update_info(); self.root.after(30,self.simulate_step)

    def draw(self):
        self.canvas.delete("pendulum"); pivot_x,pivot_y=400,50
        bob_x=pivot_x+self.length*SCALE*math.sin(self.theta); bob_y=pivot_y+self.length*SCALE*math.cos(self.theta)
        bob_x=clamp(bob_x,0,int(self.canvas["width"])); bob_y=clamp(bob_y,0,int(self.canvas["height"]))
        self.canvas.create_line(pivot_x,pivot_y,bob_x,bob_y,fill="white",width=2,tags="pendulum")
        self.canvas.create_oval(bob_x-10,bob_y-10,bob_x+10,bob_y+10,fill="blue",tags="pendulum")

    def update_info(self):
        self.info_text.set(f"Angle: {round(math.degrees(self.theta),2)}°   Angular Vel: {round(math.degrees(self.omega),2)}°/s   Time: {round(self.time_elapsed,2)} s")

    def pause_resume(self): self.paused=not self.paused
    def step_once(self): self.paused=False; self.simulate_step(); self.paused=True
    def save_results(self):
        params={"length":self.length,"theta0":math.degrees(self.theta),"damping":self.damping}
        results={"final_angle":round(math.degrees(self.theta),4),"final_angular_velocity":round(math.degrees(self.omega),4),"time":round(self.time_elapsed,4)}
        if self.user_id:self.db.save(self.user_id,"Pendulum",params,results)
    def plot_graphs(self):
        if not self.times: messagebox.showinfo("No data","Run a simulation first."); return
        angles=[math.degrees(a) for a in self.angles]; omega=[math.degrees(w) for w in self.angular_velocities]
        plt.figure(figsize=(10,4)); plt.subplot(1,2,1); plt.plot(self.times,angles); plt.xlabel("Time (s)"); plt.ylabel("Angle (deg)"); plt.title("Angle vs Time"); plt.grid()
        plt.subplot(1,2,2); plt.plot(self.times,omega); plt.xlabel("Time (s)"); plt.ylabel("Angular Velocity (deg/s)"); plt.title("Angular Velocity vs Time"); plt.grid(); plt.tight_layout(); plt.show()

class SpringMassSim(Simulation):
    def __init__(self,root,canvas,db_manager,param_frame,user_id):
        super().__init__(root,canvas,db_manager,user_id); self.param_frame=param_frame
        self.positions=[]; self.velocities=[]; self.times=[]; self.x=self.v=0; self.k=10; self.m=1; self.damping=.05; self.time_elapsed=0; self.create_ui()
    def create_ui(self):
        for w in self.param_frame.winfo_children():w.destroy()
        self.k_entry=self.create_labeled_entry("Spring Constant (N/m):","10"); self.m_entry=self.create_labeled_entry("Mass (kg):","1")
        self.x_entry=self.create_labeled_entry("Initial Displacement (m):","10"); self.v_entry=self.create_labeled_entry("Initial Velocity (m/s):","0"); self.damping_entry=self.create_labeled_entry("Damping Coefficient:","0.05")
        ttk.Button(self.param_frame,text="Start / Reset",command=self.reset_simulation).grid(row=5,column=0); ttk.Button(self.param_frame,text="Pause",command=self.pause_resume).grid(row=5,column=1); ttk.Button(self.param_frame,text="Step",command=self.step_once).grid(row=5,column=2); ttk.Button(self.param_frame,text="Show Graphs",command=self.plot_graphs).grid(row=5,column=3); ttk.Button(self.param_frame,text="Stop",command=self.stop).grid(row=5,column=5)
        self.info_text=tk.StringVar(); tk.Label(self.param_frame,textvariable=self.info_text,fg="white",bg="black",justify="left",font=("Courier",10)).grid(row=6,column=0,columnspan=6)
    def create_labeled_entry(self,label,default=""):
        row=len(self.param_frame.winfo_children())//2; tk.Label(self.param_frame,text=label,fg="white",bg="black").grid(row=row,column=0,sticky="e")
        e=ttk.Entry(self.param_frame); e.insert(0,default); e.grid(row=row,column=1,sticky="w"); return e
    def reset_simulation(self):
        try:
            self.canvas.delete("all"); self.positions.clear(); self.velocities.clear(); self.times.clear()
            self.k=float(self.k_entry.get()); self.m=float(self.m_entry.get()); self.x=float(self.x_entry.get()); self.v=float(self.v_entry.get()); self.damping=float(self.damping_entry.get()); self.time_elapsed=0
            if self.damping>10 or self.x>100: messagebox.showwarning("Input limited","Input exceeds stability limit."); self.running=False; return
            self.running=True; self.paused=False; self.simulate_step()
        except ValueError: messagebox.showerror("Error","Please enter valid numeric parameters")
    def simulate_step(self):
        if self.running and not self.paused:
            a=-(self.k/self.m)*self.x-self.damping*self.v; self.v+=a*DT; self.x+=self.v*DT; self.time_elapsed+=DT
            self.positions.append(self.x); self.velocities.append(self.v); self.times.append(self.time_elapsed); self.draw(); self.update_info(); self.root.after(30,self.simulate_step)
    def draw(self):
        self.canvas.delete("spring"); px,py=400,200; mass_y=py+self.x*20
        self.canvas.create_line(px,py,px,mass_y,fill="white",width=2,tags="spring"); self.canvas.create_oval(px-15,mass_y-15,px+15,mass_y+15,fill="red",tags="spring")
    def update_info(self): self.info_text.set(f"Displacement: {round(self.x,3)} m   Velocity: {round(self.v,3)} m/s   Time: {round(self.time_elapsed,2)} s")
    def pause_resume(self): self.paused=not self.paused
    def step_once(self): self.paused=False; self.simulate_step(); self.paused=True
    def save_results(self):
        if self.user_id:self.db.save(self.user_id,"SpringMass",{"k":self.k,"m":self.m,"x0":self.x,"v0":self.v,"damping":self.damping},{"final_displacement":round(self.x,4),"final_velocity":round(self.v,4),"time":round(self.time_elapsed,4)})
    def plot_graphs(self):
        if not self.times:messagebox.showinfo("No data","Run a simulation first.");return
        plt.figure(figsize=(10,4));plt.subplot(1,2,1);plt.plot(self.times,self.positions);plt.xlabel("Time (s)");plt.ylabel("Displacement (m)");plt.title("Displacement vs Time");plt.grid()
        plt.subplot(1,2,2);plt.plot(self.times,self.velocities);plt.xlabel("Time (s)");plt.ylabel("Velocity (m/s)");plt.title("Velocity vs Time");plt.grid();plt.tight_layout();plt.show()

class WaveSim(Simulation):
    def __init__(self,root,canvas,db_manager,param_frame,user_id):
        super().__init__(root,canvas,db_manager,user_id);self.param_frame=param_frame;self.amplitude=50;self.wavelength=100;self.speed=100;self.phase=0;self.time_history=[];self.phase_history=[];self.time_elapsed=0;self.create_ui()
    def create_ui(self):
        for w in self.param_frame.winfo_children():w.destroy()
        self.amp_entry=self.create_labeled_entry("Amplitude:","50");self.lambda_entry=self.create_labeled_entry("Wavelength:","100");self.speed_entry=self.create_labeled_entry("Speed:","100")
        ttk.Button(self.param_frame,text="Start / Reset",command=self.reset_simulation).grid(row=5,column=0);ttk.Button(self.param_frame,text="Pause / Resume",command=self.pause_resume).grid(row=5,column=1);ttk.Button(self.param_frame,text="Step",command=self.step_once).grid(row=5,column=2);ttk.Button(self.param_frame,text="Show Graphs",command=self.plot_graphs).grid(row=5,column=3);ttk.Button(self.param_frame,text="Show Previous",command=self.show_previous_simulations).grid(row=5,column=4)
        self.info_text=tk.StringVar();tk.Label(self.param_frame,textvariable=self.info_text,fg="white",bg="black",justify="left",font=("Courier",10)).grid(row=6,column=0,columnspan=6)
    def create_labeled_entry(self,label,default=""):
        row=len(self.param_frame.winfo_children())//2;tk.Label(self.param_frame,text=label,fg="white",bg="black").grid(row=row,column=0,sticky="e");e=ttk.Entry(self.param_frame);e.insert(0,default);e.grid(row=row,column=1,sticky="w");return e
    def reset_simulation(self):
        try:
            self.canvas.delete("all");self.time_history.clear();self.phase_history.clear();self.time_elapsed=0;self.amplitude=float(self.amp_entry.get());self.wavelength=float(self.lambda_entry.get());self.speed=float(self.speed_entry.get());self.phase=0;self.running=True;self.paused=False;self.simulate_step();self.save_results()
        except ValueError:messagebox.showerror("Error","Please enter valid numeric parameters")
    def simulate_step(self):
        if self.running and not self.paused:
            self.phase+=(2*math.pi*self.speed/self.wavelength)*DT;self.time_elapsed+=DT;self.time_history.append(self.time_elapsed);self.phase_history.append(self.phase);self.draw();self.update_info();self.root.after(30,self.simulate_step)
    def draw(self):
        self.canvas.delete("wave");points=[];y_center=200
        for x in range(0,900,5):points.append((x,y_center+self.amplitude*math.sin(2*math.pi*x/self.wavelength-self.phase)))
        for i in range(len(points)-1):self.canvas.create_line(points[i],points[i+1],fill="green",width=2,tags="wave")
    def update_info(self):self.info_text.set(f"Phase: {round(self.phase,2)} rad   Time: {round(self.time_elapsed,2)} s")
    def pause_resume(self):self.paused=not self.paused
    def step_once(self):self.paused=False;self.simulate_step();self.paused=True
    def save_results(self):
        if self.user_id:self.db.save(self.user_id,"Wave",{"amplitude":self.amplitude,"wavelength":self.wavelength,"speed":self.speed},{"phase":self.phase,"time":self.time_elapsed})
    def plot_graphs(self):
        if not self.time_history:messagebox.showinfo("No data","Run a simulation first.");return
        plt.plot(self.time_history,self.phase_history);plt.xlabel("Time (s)");plt.ylabel("Phase (rad)");plt.title("Wave Phase vs Time");plt.grid();plt.show()
    def show_previous_simulations(self):
        results=self.db.load_all(self.user_id,"Wave");self.info_text.set("Previous Wave Simulations:\n\n"+"".join(f"Params: {r[3]}, Results: {r[4]}, Date: {r[5]}\n" for r in results))

class CircularMotionSim(Simulation):
    def __init__(self,root,canvas,db_manager,param_frame,user_id):
        super().__init__(root,canvas,db_manager,user_id);self.param_frame=param_frame;self.radius=100;self.omega=1;self.theta=0;self.time_elapsed=0;self.positions=[];self.velocities=[];self.times=[];self.create_ui()
    def create_ui(self):
        for w in self.param_frame.winfo_children():w.destroy()
        self.radius_entry=self.create_labeled_entry("Radius (m):","1");self.omega_entry=self.create_labeled_entry("Angular Velocity (rad/s):","1")
        ttk.Button(self.param_frame,text="Start / Reset",command=self.reset_simulation).grid(row=2,column=0);ttk.Button(self.param_frame,text="Pause / Resume",command=self.pause_resume).grid(row=2,column=1);ttk.Button(self.param_frame,text="Step",command=self.step_once).grid(row=2,column=2);ttk.Button(self.param_frame,text="Show Graphs",command=self.plot_graphs).grid(row=2,column=3);ttk.Button(self.param_frame,text="Stop",command=self.stop).grid(row=2,column=5)
        self.info_text=tk.StringVar();tk.Label(self.param_frame,textvariable=self.info_text,fg="white",bg="black",justify="left",font=("Courier",10)).grid(row=3,column=0,columnspan=6)
    def create_labeled_entry(self,label,default=""):
        row=len(self.param_frame.winfo_children())//2;tk.Label(self.param_frame,text=label,fg="white",bg="black").grid(row=row,column=0,sticky="e");e=ttk.Entry(self.param_frame);e.insert(0,default);e.grid(row=row,column=1,sticky="w");return e
    def reset_simulation(self):
        try:
            self.canvas.delete("all");self.positions.clear();self.velocities.clear();self.times.clear();self.theta=0;self.time_elapsed=0;self.radius=float(self.radius_entry.get());self.omega=float(self.omega_entry.get())
            if self.radius>100 or self.omega>100:messagebox.showwarning("Input limited","Radius and angular velocity capped at 100 for stability.");self.running=False;return
            self.running=True;self.paused=False;self.simulate_step()
        except ValueError:messagebox.showerror("Error","Please enter valid numeric parameters")
    def simulate_step(self):
        if self.running and not self.paused:
            self.theta+=self.omega*DT;x=self.radius*math.cos(self.theta);y=self.radius*math.sin(self.theta);self.positions.append((x,y));self.velocities.append(self.omega*self.radius);self.time_elapsed+=DT;self.times.append(self.time_elapsed);self.draw(x,y);self.update_info(x,y);self.root.after(30,self.simulate_step)
    def draw(self,x,y):
        self.canvas.delete("circle");cx,cy=400,200;scale=100;px=cx+x*scale;py=cy+y*scale
        self.canvas.create_oval(cx-self.radius*scale,cy-self.radius*scale,cx+self.radius*scale,cy+self.radius*scale,outline="white",tags="circle");self.canvas.create_oval(px-10,py-10,px+10,py+10,fill="red",tags="circle");self.canvas.create_line(cx,cy,px,py,fill="yellow",tags="circle")
    def update_info(self,x,y):self.info_text.set(f"x: {round(x,3)} m   y: {round(y,3)} m   Time: {round(self.time_elapsed,2)} s")
    def pause_resume(self):self.paused=not self.paused
    def step_once(self):self.paused=False;self.simulate_step();self.paused=True
    def save_results(self):
        if self.user_id and self.positions:self.db.save(self.user_id,"CircularMotion",{"radius":self.radius,"omega":self.omega},{"final_x":round(self.positions[-1][0],4),"final_y":round(self.positions[-1][1],4),"time":round(self.time_elapsed,4)})
    def plot_graphs(self):
        if not self.times:messagebox.showinfo("No data","Run a simulation first.");return
        xs,ys=zip(*self.positions);plt.figure(figsize=(10,4));plt.subplot(1,2,1);plt.plot(xs,ys);plt.xlabel("X (m)");plt.ylabel("Y (m)");plt.title("Path of Circular Motion");plt.grid();plt.subplot(1,2,2);plt.plot(self.times,self.velocities);plt.xlabel("Time (s)");plt.ylabel("Tangential Velocity (m/s)");plt.title("Velocity vs Time");plt.grid();plt.tight_layout();plt.show()

class SimulationApp:
    def __init__(self,root,user_id,db_manager,username):
        self.root,self.user_id,self.db,self.username=root,user_id,db_manager,username;self.current_sim=None;self.build_ui()
    def build_ui(self):
        for w in self.root.winfo_children():w.destroy()
        self.root.title("ProjectiFy Simulations");self.root.configure(bg="black")
        self.top_frame=tk.Frame(self.root,bg="black");self.top_frame.pack(side="top",fill="x")
        for name,cmd in [("Projectile",self.load_projectile),("Pendulum",self.load_pendulum),("Spring",self.load_spring),("Wave",self.load_wave),("Circular",self.load_circular)]:
            ttk.Button(self.top_frame,text=name,command=cmd).pack(side="left")
        ttk.Button(self.top_frame,text="Back to Profile",command=self.back_to_profile).pack(side="right")
        canvas_frame=tk.Frame(self.root);canvas_frame.pack(side="left",padx=10,pady=10)
        self.canvas=tk.Canvas(canvas_frame,width=800,height=600,bg="black",scrollregion=(0,0,3000,1000));self.canvas.pack(side="left")
        x_scroll=ttk.Scrollbar(canvas_frame,orient="horizontal",command=self.canvas.xview);y_scroll=ttk.Scrollbar(canvas_frame,orient="vertical",command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=x_scroll.set,yscrollcommand=y_scroll.set);x_scroll.pack(side="bottom",fill="x");y_scroll.pack(side="right",fill="y")
        self.param_frame=tk.Frame(self.root,bg="black");self.param_frame.pack(side="right",fill="y",padx=10,pady=10)
    def switch(self,cls):
        if self.current_sim:self.current_sim.stop()
        self.current_sim=cls(self.root,self.canvas,self.db,self.param_frame,self.user_id)
    def load_projectile(self):self.switch(ProjectileSim)
    def load_pendulum(self):self.switch(PendulumSim)
    def load_spring(self):self.switch(SpringMassSim)
    def load_wave(self):self.switch(WaveSim)
    def load_circular(self):self.switch(CircularMotionSim)
    def back_to_profile(self):
        if self.current_sim:self.current_sim.stop()
        ProfileScreen(self.root,self.db,self.user_id,self.username)

def main():
    root=tk.Tk();db_manager=DatabaseManager();LoginScreen(root,db_manager);root.mainloop()

if __name__=="__main__":
    main()
