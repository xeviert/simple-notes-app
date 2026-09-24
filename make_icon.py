from PIL import Image, ImageDraw

SIZE = 256


def draw():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fold = 56
    left, top, right, bottom = 36, 20, 220, 236

    d.rounded_rectangle((left + 6, top + 8, right + 6, bottom + 8), radius=18, fill=(0, 0, 0, 60))
    d.rounded_rectangle((left, top, right, bottom), radius=18, fill=(255, 214, 90))
    # Cut the top-right corner and draw the folded flap.
    d.polygon([(right - fold, top), (right + 1, top), (right + 1, top + fold)], fill=(0, 0, 0, 0))
    d.polygon([(right - fold, top), (right - fold, top + fold), (right, top + fold)], fill=(230, 176, 40))

    d.rounded_rectangle((left, top, right - fold, top + 44), radius=18, fill=(245, 166, 35))
    d.rectangle((left, top + 26, right - fold, top + 44), fill=(245, 166, 35))
    d.polygon([(right - fold, top + 26), (right - fold, top + 44), (right - fold + 18, top + 44)], fill=(245, 166, 35))

    for y in range(top + 82, bottom - 20, 34):
        d.rounded_rectangle((left + 28, y, right - 28, y + 10), radius=5, fill=(160, 110, 20))
    return img


if __name__ == "__main__":
    draw().save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    draw().save("icon.png")
