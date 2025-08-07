import os
from PIL import Image
import struct


def verify_ico_file(ico_path):
    """Verify if an ICO file is properly formatted"""
    print(f"Checking icon file: {ico_path}")

    # Check if file exists
    if not os.path.exists(ico_path):
        print("❌ Icon file does not exist!")
        return False

    # Check file size
    file_size = os.path.getsize(ico_path)
    print(f"📁 File size: {file_size} bytes")

    try:
        # Try to open with PIL
        with Image.open(ico_path) as img:
            print(f"✅ PIL can read the file")
            print(f"📐 Format: {img.format}")
            print(f"📏 Size: {img.size}")
            print(f"🎨 Mode: {img.mode}")

            # Check if it's actually an ICO
            if img.format != 'ICO':
                print("⚠️  File is not in ICO format!")
                return False

        # Read ICO header to check for multiple sizes
        with open(ico_path, 'rb') as f:
            # ICO header: 6 bytes
            header = f.read(6)
            if len(header) < 6:
                print("❌ Invalid ICO header")
                return False

            # Parse header
            reserved, type_field, count = struct.unpack('<HHH', header)

            if reserved != 0 or type_field != 1:
                print("❌ Invalid ICO file signature")
                return False

            print(f"🔢 Number of icon sizes: {count}")

            if count == 0:
                print("❌ No icons found in file")
                return False

            # Read directory entries
            sizes = []
            for i in range(count):
                entry = f.read(16)
                if len(entry) < 16:
                    break
                width, height = struct.unpack('<BB', entry[:2])
                # Width/height of 0 means 256
                width = width if width != 0 else 256
                height = height if height != 0 else 256
                sizes.append(f"{width}x{height}")

            print(f"📐 Available sizes: {', '.join(sizes)}")

        print("✅ Icon file appears to be valid!")
        return True

    except Exception as e:
        print(f"❌ Error reading icon file: {e}")
        return False


def create_test_icon():
    """Create a simple test icon to verify PyInstaller works"""
    from PIL import Image, ImageDraw

    # Create a simple icon with multiple sizes
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []

    for size in sizes:
        # Create a simple colored square
        img = Image.new('RGBA', size, (70, 130, 180, 255))  # Steel blue
        draw = ImageDraw.Draw(img)

        # Draw a simple "N" for NetDog
        text_size = size[0] // 2
        try:
            draw.text((size[0] // 4, size[1] // 4), "N", fill=(255, 255, 255, 255))
        except:
            # If text drawing fails, just use a colored square
            pass

        images.append(img)

    # Save as ICO
    test_icon_path = "test_netdog.ico"
    images[0].save(test_icon_path, format='ICO', sizes=[img.size for img in images])
    print(f"✅ Created test icon: {test_icon_path}")
    return test_icon_path


if __name__ == "__main__":
    # Check your current icon
    icon_path = "NetDog_icon_highres.ico"

    print("=" * 50)
    print("ICON VERIFICATION")
    print("=" * 50)

    is_valid = verify_ico_file(icon_path)

    if not is_valid:
        print("\n" + "=" * 50)
        print("CREATING TEST ICON")
        print("=" * 50)
        test_icon = create_test_icon()
        print(f"\nTry building with: --icon={test_icon}")

    print("\n" + "=" * 50)
    print("PYINSTALLER COMMAND SUGGESTIONS")
    print("=" * 50)

    if is_valid:
        print("Your icon appears valid. Try these commands:")
    else:
        print("Your icon has issues. Try these with the test icon:")

    current_dir = os.getcwd().replace("\\", "\\\\")
    icon_file = "test_netdog.ico" if not is_valid else "NetDog_icon_highres.ico"

    print(f'\n1. With absolute path:')
    print(
        f'pyinstaller --onefile --windowed --icon="{current_dir}\\{icon_file}" --name "NetDog Network Diagnostics" netdog.py')

    print(f'\n2. Clean build:')
    print(
        f'rmdir /s build dist & del "NetDog Network Diagnostics.spec" & pyinstaller --onefile --windowed --icon={icon_file} --name "NetDog Network Diagnostics" netdog.py')

    print(f'\n3. With UPX disabled (sometimes helps):')
    print(f'pyinstaller --onefile --windowed --noupx --icon={icon_file} --name "NetDog Network Diagnostics" netdog.py')