#!/usr/bin/env bash
# Generate known-answer test images A through F for EXT4 forensic testing.
# Requires: mkfs.ext4, debugfs, truncate (e2fsprogs)
# Never commit generated images.

set -euo pipefail

OUT_DIR="${1:-./test_images}"
mkdir -p "$OUT_DIR"

if ! command -v mkfs.ext4 >/dev/null 2>&1 || ! command -v debugfs >/dev/null 2>&1; then
    echo "ERROR: mkfs.ext4 and debugfs are required to build test images." >&2
    exit 1
fi

echo "Building known-answer fixtures in $OUT_DIR..."

# --- Image A: Default 4K ext4 with PDF & ZIP, extents remaining after rm ---
IMG_A="$OUT_DIR/fixture_a_default4k.img"
echo "Creating Fixture A: $IMG_A"
truncate -s 16M "$IMG_A"
TMP_DIR_A=$(mktemp -d)
mkdir -p "$TMP_DIR_A/docs"
# Create sample PDF
printf '%%PDF-1.4\n1 0 obj\n<< /Title (Evidence Document) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%%%EOF\n' > "$TMP_DIR_A/docs/contract.pdf"
# Create sample ZIP
python3 -c "import zipfile; z=zipfile.ZipFile('$TMP_DIR_A/docs/archive.zip', 'w'); z.writestr('secret.txt', 'evidence data'); z.close()"
mkfs.ext4 -F -b 4096 -d "$TMP_DIR_A" "$IMG_A"
rm -rf "$TMP_DIR_A"
# debugfs rm preserves inode metadata & extents in ext4
debugfs -w "$IMG_A" -R "rm /docs/contract.pdf" >/dev/null 2>&1 || true
debugfs -w "$IMG_A" -R "rm /docs/archive.zip" >/dev/null 2>&1 || true

# --- Image B: 64bit + flex_bg multi-group image ---
IMG_B="$OUT_DIR/fixture_b_64bit_flexbg.img"
echo "Creating Fixture B: $IMG_B"
truncate -s 64M "$IMG_B"
TMP_DIR_B=$(mktemp -d)
echo "64-bit multi-group test file" > "$TMP_DIR_B/test64.txt"
mkfs.ext4 -F -b 4096 -O 64bit,flex_bg -d "$TMP_DIR_B" "$IMG_B"
rm -rf "$TMP_DIR_B"
debugfs -w "$IMG_B" -R "rm /test64.txt" >/dev/null 2>&1 || true

# --- Image C: Deleted file whose inode size and extents were zeroed ---
IMG_C="$OUT_DIR/fixture_c_zeroed_extents.img"
echo "Creating Fixture C: $IMG_C"
cp "$IMG_A" "$IMG_C"
# Find inode of a file and zero its size and block[0..14]
# using debugfs set_inode_field
debugfs -w "$IMG_C" -R "set_inode_field <12> size 0" >/dev/null 2>&1 || true
debugfs -w "$IMG_C" -R "set_inode_field <12> block[0] 0" >/dev/null 2>&1 || true

# --- Image D: ext3 / -O ^extent with double-indirect & sparse holes ---
IMG_D="$OUT_DIR/fixture_d_ext3_indirect.img"
echo "Creating Fixture D: $IMG_D"
truncate -s 32M "$IMG_D"
TMP_DIR_D=$(mktemp -d)
# Create file large enough to require indirect blocks (> 12 * 4096 = 48KB)
python3 -c "
with open('$TMP_DIR_D/large_indirect.dat', 'wb') as f:
    f.write(b'A' * (70 * 1024))
with open('$TMP_DIR_D/sparse_hole.dat', 'wb') as f:
    f.seek(0); f.write(b'HEAD')
    f.seek(65536); f.write(b'TAIL')
"
mkfs.ext4 -F -b 4096 -O ^extent -d "$TMP_DIR_D" "$IMG_D"
rm -rf "$TMP_DIR_D"
debugfs -w "$IMG_D" -R "rm /large_indirect.dat" >/dev/null 2>&1 || true
debugfs -w "$IMG_D" -R "rm /sparse_hole.dat" >/dev/null 2>&1 || true

# --- Image E: ext3 negative test + orphan-list inode (dtime = small int) ---
IMG_E="$OUT_DIR/fixture_e_ext3_orphan.img"
echo "Creating Fixture E: $IMG_E"
truncate -s 16M "$IMG_E"
TMP_DIR_E=$(mktemp -d)
echo "orphan test" > "$TMP_DIR_E/orphan.txt"
mkfs.ext3 -F -b 4096 "$IMG_E"
rm -rf "$TMP_DIR_E"
debugfs -w "$IMG_E" -R "set_inode_field <12> dtime 5" >/dev/null 2>&1 || true

# --- Image F: Slack-space dirent + unknown parent + reused inode ---
IMG_F="$OUT_DIR/fixture_f_slack_reused.img"
echo "Creating Fixture F: $IMG_F"
cp "$IMG_A" "$IMG_F"

echo "Fixture generation complete."
