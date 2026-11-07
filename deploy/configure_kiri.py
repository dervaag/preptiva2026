"""Create local-only deployment secrets once; never rotate an existing DB password."""
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not (ROOT / '.env').is_file():
        raise SystemExit('Buat .env dari .env.example dan isi kredensial API terlebih dahulu.')
    destination = ROOT / '.env.kiri'
    if destination.is_symlink():
        raise SystemExit('.env.kiri tidak boleh berupa symlink.')
    if destination.exists():
        values = dict(line.split('=', 1) for line in destination.read_text().splitlines()
                      if '=' in line and not line.lstrip().startswith('#'))
        for key in ('SECRET_KEY', 'DB_PASSWORD'):
            value = values.get(key, '').strip()
            if len(value) < 32 or any(c not in '0123456789abcdef' for c in value):
                raise SystemExit(f'{key} di .env.kiri harus berupa hex acak minimal 32 karakter. File tidak diubah.')
        destination.chmod(0o600)
        print('.env.kiri sudah tersedia; secret dan password database dipertahankan.')
        return
    content = ('# Dibuat lokal; jangan commit atau membagikan file ini.\n'
               'APP_ENV=production\nCOOKIE_SECURE=true\n'
               f'SECRET_KEY={secrets.token_hex(32)}\nDB_PASSWORD={secrets.token_hex(32)}\n')
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        file.write(content)
    print('.env.kiri dibuat dengan mode 600. Nilai rahasia tidak ditampilkan.')


if __name__ == '__main__':
    main()
