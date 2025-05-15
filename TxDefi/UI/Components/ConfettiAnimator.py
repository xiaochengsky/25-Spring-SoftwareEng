import tkinter as tk
import random
from TxDefi.Utilities.SoundUtils import SoundUtils, SoundType

class ConfettiAnimator:
    def __init__(self, root, canvas: tk.Canvas, sound_utils: SoundUtils, is_muted = True):
        self.root = root
        self.canvas = canvas
        self.confetti_particles = []
        self.gravity = 1.2  # Acceleration due to gravity
        # Bind window resize event to update canvas size
        self.root.bind("<Configure>", self.update_canvas_size)

        self.canvas_width = 1
        self.canvas_height = 1
        self.is_muted = is_muted
        self.sound_utils = sound_utils

    def update_canvas_size(self, event):
        """Update canvas dimensions on window resize."""
        self.canvas_width = self.canvas.winfo_width()
        self.canvas_height = self.canvas.winfo_height()

    def show_confetti(self):
        """Create confetti and animate them with an upward throw and downward acceleration."""

        try:            
            for _ in range(50):  # Number of confetti pieces
                x = self.canvas_width/2#random.randint(10, self.canvas_width - 10)  # Ensure within canvas bounds
                y = self.canvas_height/2 # Start from near the bottom
                width = random.randint(10, 20)  # Random width
                height = random.randint(4, 10)  # Random height
                color = random.choice(["red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"])
                angle = random.uniform(-30, 30)  # Slightly tilted throwing angle
                velocity = random.uniform(10, 18)  # Initial upward velocity

                confetti = self.canvas.create_rectangle(x, y, x + width, y + height, fill=color, outline=color)
                self.confetti_particles.append({
                    "id": confetti,
                    "vx": random.uniform(-3, 3),  # Sideways velocity
                    "vy": -velocity,  # Initial upward velocity
                    "angle": angle,
                    "rotation_speed": random.uniform(-5, 5),  # Random spin
                })

            self.animate_confetti()
            
            if not self.is_muted and self.sound_utils:
                self.sound_utils.play_sound(SoundType.CELEBRATE)
        except Exception as e:
            print("Celebrate failed. Try installing pygame for cross-platform support." + str(e))

    def animate_confetti(self):
        """Move confetti in a natural arc and let them accelerate downwards."""
        active_particles = []
        for particle in self.confetti_particles:
            confetti = particle["id"]
            vx, vy = particle["vx"], particle["vy"]
            angle = particle["angle"]
            rotation_speed = particle["rotation_speed"]

            # Update velocity due to gravity
            vy += self.gravity

            # Move confetti based on velocity
            self.canvas.move(confetti, vx, vy)

            # Simulate rotation (not directly visible in tkinter, but included for realism)
            particle["angle"] += rotation_speed

            try:
                # Get new coordinates
                x1, y1, x2, y2 = self.canvas.coords(confetti)

                # Remove confetti when it exits the bottom
                if y1 < self.canvas_height:
                    particle["vy"] = vy
                    active_particles.append(particle)
                else:
                    self.canvas.delete(confetti)  # Remove when it falls out of view
            except Exception as e:
                pass
            
        self.confetti_particles = active_particles  # Update the active list
        if self.confetti_particles:
            self.root.after(30, self.animate_confetti)  # Faster frame rate for smooth animation

if __name__ == "__main__":
    root = tk.Tk()
    app = ConfettiAnimator(root)
    root.mainloop()
