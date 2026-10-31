import os
from PIL import Image, ImageDraw

def generate_all_sprites(base_dir):
    os.makedirs(base_dir, exist_ok=True)
    
    # Palette
    CAT_ORANGE = (255, 145, 30, 255)
    CAT_DARK = (215, 105, 10, 255)
    CAT_LIGHT = (255, 185, 90, 255)
    EYE_WHITE = (255, 255, 255, 255)
    EYE_PUPIL = (30, 30, 40, 255)
    NOSE_PINK = (255, 130, 150, 255)
    CHEEK_PINK = (255, 150, 170, 180)
    EXCLAMATION = (255, 40, 40, 255)
    HEART_RED = (255, 60, 90, 255)
    ZZZ_BLUE = (100, 180, 255, 255)

    def draw_idle_frame(frame_idx):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Breathing shift
        dy = 1 if frame_idx in (1, 2) else 0

        # Body
        draw.rectangle([8, 14 + dy, 24, 27 + dy], fill=CAT_ORANGE)
        draw.rectangle([10, 16 + dy, 22, 27 + dy], fill=CAT_LIGHT) # Belly
        # Paws
        draw.rectangle([9, 27 + dy, 13, 29 + dy], fill=CAT_DARK)
        draw.rectangle([19, 27 + dy, 23, 29 + dy], fill=CAT_DARK)

        # Head
        draw.rectangle([7, 8 + dy, 25, 18 + dy], fill=CAT_ORANGE)
        # Ears (outer & inner)
        draw.polygon([(7, 8 + dy), (12, 8 + dy), (8, 3 + dy)], fill=CAT_ORANGE)
        draw.polygon([(8, 8 + dy), (11, 8 + dy), (9, 5 + dy)], fill=NOSE_PINK)
        draw.polygon([(25, 8 + dy), (20, 8 + dy), (24, 3 + dy)], fill=CAT_ORANGE)
        draw.polygon([(24, 8 + dy), (21, 8 + dy), (23, 5 + dy)], fill=NOSE_PINK)

        # Tail flicking
        tail_tip_y = 17 + dy + (1 if frame_idx % 2 == 0 else -1)
        draw.line([(7, 23 + dy), (4, 21 + dy), (3, tail_tip_y)], fill=CAT_DARK, width=2)

        # Eye sockets (white, pupil will be overlaid / centered by default)
        draw.rectangle([10, 11 + dy, 14, 15 + dy], fill=EYE_WHITE)
        draw.rectangle([18, 11 + dy, 22, 15 + dy], fill=EYE_WHITE)
        # Base pupil
        draw.rectangle([12, 12 + dy, 13, 14 + dy], fill=EYE_PUPIL)
        draw.rectangle([20, 12 + dy, 21, 14 + dy], fill=EYE_PUPIL)

        # Nose & mouth
        draw.point([(16, 15 + dy)], fill=NOSE_PINK)
        draw.point([(15, 16 + dy), (17, 16 + dy)], fill=CAT_DARK)
        return img

    def draw_walk_frame(frame_idx):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        bob = 1 if frame_idx in (1, 3) else 0

        # Body (side view)
        draw.rectangle([6, 13 + bob, 23, 23 + bob], fill=CAT_ORANGE)
        draw.rectangle([12, 17 + bob, 22, 23 + bob], fill=CAT_LIGHT) # Chest

        # Head
        draw.rectangle([17, 8 + bob, 28, 18 + bob], fill=CAT_ORANGE)
        # Ears
        draw.polygon([(18, 8 + bob), (22, 8 + bob), (19, 3 + bob)], fill=CAT_ORANGE)
        draw.polygon([(24, 8 + bob), (28, 8 + bob), (27, 3 + bob)], fill=CAT_ORANGE)
        draw.polygon([(25, 8 + bob), (27, 8 + bob), (26, 5 + bob)], fill=NOSE_PINK)

        # Eye socket & pupil
        draw.rectangle([22, 11 + bob, 26, 15 + bob], fill=EYE_WHITE)
        draw.rectangle([24, 12 + bob, 25, 14 + bob], fill=EYE_PUPIL)

        # Nose
        draw.rectangle([27, 14 + bob, 28, 15 + bob], fill=NOSE_PINK)

        # Tail
        tail_bob = -1 if frame_idx in (0, 2) else 1
        draw.line([(6, 16 + bob), (2, 14 + bob + tail_bob), (1, 10 + bob + tail_bob)], fill=CAT_DARK, width=2)

        # Animated 4-step legs
        leg_positions = [
            # Front leg 1, Front leg 2, Back leg 1, Back leg 2
            [(20, 23 + bob, 23, 28 + bob), (16, 23 + bob, 19, 27 + bob), (10, 23 + bob, 13, 28 + bob), (7, 23 + bob, 10, 26 + bob)],
            [(19, 23 + bob, 22, 27 + bob), (18, 23 + bob, 21, 28 + bob), (8, 23 + bob, 11, 27 + bob), (9, 23 + bob, 12, 28 + bob)],
            [(17, 23 + bob, 20, 27 + bob), (21, 23 + bob, 24, 28 + bob), (7, 23 + bob, 10, 26 + bob), (11, 23 + bob, 14, 28 + bob)],
            [(18, 23 + bob, 21, 28 + bob), (19, 23 + bob, 22, 27 + bob), (9, 23 + bob, 12, 28 + bob), (8, 23 + bob, 11, 27 + bob)],
        ]
        current_legs = leg_positions[frame_idx % 4]
        for idx, leg in enumerate(current_legs):
            color = CAT_ORANGE if idx in (0, 2) else CAT_DARK
            draw.rectangle(leg, fill=color)

        return img

    def draw_react_frame(frame_idx):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Excited jump pose
        jump_y = -2 if frame_idx in (1, 2) else 0

        # Body
        draw.rectangle([8, 13 + jump_y, 24, 25 + jump_y], fill=CAT_ORANGE)
        draw.rectangle([10, 16 + jump_y, 22, 25 + jump_y], fill=CAT_LIGHT)

        # Paws spread out
        draw.rectangle([5, 18 + jump_y, 8, 22 + jump_y], fill=CAT_ORANGE)
        draw.rectangle([24, 18 + jump_y, 27, 22 + jump_y], fill=CAT_ORANGE)
        draw.rectangle([9, 25 + jump_y, 13, 28 + jump_y], fill=CAT_DARK)
        draw.rectangle([19, 25 + jump_y, 23, 28 + jump_y], fill=CAT_DARK)

        # Head
        draw.rectangle([7, 7 + jump_y, 25, 17 + jump_y], fill=CAT_ORANGE)
        # Perked high ears
        draw.polygon([(7, 7 + jump_y), (12, 7 + jump_y), (7, 1 + jump_y)], fill=CAT_ORANGE)
        draw.polygon([(8, 7 + jump_y), (11, 7 + jump_y), (8, 3 + jump_y)], fill=NOSE_PINK)
        draw.polygon([(25, 7 + jump_y), (20, 7 + jump_y), (25, 1 + jump_y)], fill=CAT_ORANGE)
        draw.polygon([(24, 7 + jump_y), (21, 7 + jump_y), (24, 3 + jump_y)], fill=NOSE_PINK)

        # Big surprised eyes (round 5x5)
        draw.rectangle([9, 9 + jump_y, 14, 14 + jump_y], fill=EYE_WHITE)
        draw.rectangle([18, 9 + jump_y, 23, 14 + jump_y], fill=EYE_WHITE)
        # Pupils
        draw.rectangle([11, 10 + jump_y, 13, 13 + jump_y], fill=EYE_PUPIL)
        draw.rectangle([20, 10 + jump_y, 22, 13 + jump_y], fill=EYE_PUPIL)

        # Open little mouth 'o'
        draw.rectangle([15, 15 + jump_y, 17, 17 + jump_y], fill=NOSE_PINK)

        # Exclamation mark or sparkles
        if frame_idx in (0, 1):
            draw.rectangle([27, 2 + jump_y, 28, 6 + jump_y], fill=EXCLAMATION)
            draw.rectangle([27, 8 + jump_y, 28, 9 + jump_y], fill=EXCLAMATION)
        else:
            # Sparkle
            draw.point([(27, 4 + jump_y), (28, 3 + jump_y), (28, 5 + jump_y), (29, 4 + jump_y)], fill=EXCLAMATION)

        return img

    def draw_sated_frame(frame_idx):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        dy = 1 if frame_idx in (1, 3) else 0

        # Body
        draw.rectangle([7, 13 + dy, 25, 27 + dy], fill=CAT_ORANGE)
        draw.rectangle([10, 16 + dy, 22, 27 + dy], fill=CAT_LIGHT)
        # Paws resting
        draw.rectangle([9, 26 + dy, 13, 28 + dy], fill=CAT_DARK)
        draw.rectangle([19, 26 + dy, 23, 28 + dy], fill=CAT_DARK)

        # Head
        draw.rectangle([7, 7 + dy, 25, 17 + dy], fill=CAT_ORANGE)
        # Ears
        draw.polygon([(7, 7 + dy), (12, 7 + dy), (8, 2 + dy)], fill=CAT_ORANGE)
        draw.polygon([(25, 7 + dy), (20, 7 + dy), (24, 2 + dy)], fill=CAT_ORANGE)

        # Happy closed curved eyes ^.^
        draw.line([(10, 13 + dy), (12, 11 + dy), (14, 13 + dy)], fill=EYE_PUPIL, width=1)
        draw.line([(18, 13 + dy), (20, 11 + dy), (22, 13 + dy)], fill=EYE_PUPIL, width=1)

        # Blushing pink cheeks
        draw.rectangle([8, 14 + dy, 10, 15 + dy], fill=CHEEK_PINK)
        draw.rectangle([22, 14 + dy, 24, 15 + dy], fill=CHEEK_PINK)

        # Smile
        draw.point([(16, 14 + dy)], fill=NOSE_PINK)
        draw.line([(14, 16 + dy), (16, 17 + dy), (18, 16 + dy)], fill=CAT_DARK)

        # Floating heart
        heart_y = 3 + (frame_idx % 2)
        draw.polygon([(27, heart_y + 1), (26, heart_y), (28, heart_y)], fill=HEART_RED)
        draw.polygon([(29, heart_y + 1), (28, heart_y), (30, heart_y)], fill=HEART_RED)
        draw.polygon([(26, heart_y + 1), (30, heart_y + 1), (28, heart_y + 4)], fill=HEART_RED)

        return img

    def draw_sleep_frame(frame_idx):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Sleeping curled up cat
        dy = 1 if frame_idx in (1, 2) else 0

        # Curled body
        draw.ellipse([6, 16 + dy, 26, 28 + dy], fill=CAT_ORANGE)
        # Curled tail wrapped around
        draw.arc([4, 18 + dy, 12, 28 + dy], start=90, end=270, fill=CAT_DARK, width=2)

        # Head resting low
        draw.ellipse([14, 14 + dy, 28, 26 + dy], fill=CAT_ORANGE)
        # Ears drooped back
        draw.polygon([(23, 15 + dy), (27, 14 + dy), (28, 18 + dy)], fill=CAT_DARK)
        draw.polygon([(18, 14 + dy), (22, 13 + dy), (21, 17 + dy)], fill=CAT_DARK)

        # Closed sleeping eyes - -
        draw.line([(18, 20 + dy), (21, 20 + dy)], fill=EYE_PUPIL, width=1)
        draw.line([(23, 20 + dy), (26, 20 + dy)], fill=EYE_PUPIL, width=1)
        draw.point([(22, 22 + dy)], fill=NOSE_PINK)

        # Zzz bubbles floating
        z_offset = frame_idx
        draw.text((6, 9 - z_offset), "z", fill=ZZZ_BLUE)
        if frame_idx >= 2:
            draw.text((2, 3 - (z_offset - 2)), "Z", fill=ZZZ_BLUE)

        return img

    generators = {
        "idle": draw_idle_frame,
        "walk": draw_walk_frame,
        "react": draw_react_frame,
        "sated": draw_sated_frame,
        "sleep": draw_sleep_frame,
    }

    for state, gen_func in generators.items():
        state_dir = os.path.join(base_dir, state)
        os.makedirs(state_dir, exist_ok=True)
        frames = [gen_func(i) for i in range(4)]
        
        # Save individual frame files
        for i, frame in enumerate(frames, start=1):
            frame.save(os.path.join(state_dir, f"{i:02d}.png"))
            frame.save(os.path.join(state_dir, f"{state}_{i:02d}.png"))
        
        # Save composite spritesheet (horizontal 128x32)
        sheet = Image.new("RGBA", (32 * len(frames), 32), (0, 0, 0, 0))
        for i, frame in enumerate(frames):
            sheet.paste(frame, (i * 32, 0))
        
        sheet.save(os.path.join(base_dir, f"{state}_sheet.png"))
        sheet.save(os.path.join(base_dir, f"{state}.png"))
        sheet.save(os.path.join(state_dir, "spritesheet.png"))

        # Also support legacy names like Black-Idle.png / Black-Run.png
        if state == "idle":
            sheet.save(os.path.join(state_dir, "Black-Idle.png"))
            sheet.save(os.path.join(base_dir, "sprites", "Black-Idle.png") if os.path.exists(os.path.join(base_dir, "sprites")) else os.path.join(base_dir, "Black-Idle.png"))
        elif state == "walk":
            sheet.save(os.path.join(state_dir, "Black-Run.png"))
            sheet.save(os.path.join(base_dir, "sprites", "Black-Run.png") if os.path.exists(os.path.join(base_dir, "sprites")) else os.path.join(base_dir, "Black-Run.png"))

    print(f"Generated all spritesheets and frames successfully in {base_dir}")

if __name__ == "__main__":
    assets_sprites = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "sprites"))
    generate_all_sprites(assets_sprites)
