"""Local/server-shell bootstrap (offline DB access): avoids putting passwords on CLI."""
import getpass
import sys

from app import StaffCreate, _create_staff, connection, init_db


def main():
    if len(sys.argv) != 2 or sys.argv[1] != "create-admin":
        print("Sử dụng: python manage_staff.py create-admin", file=sys.stderr)
        return 2
    init_db()
    with connection() as db:
        if db.execute("SELECT 1 FROM staff_users LIMIT 1").fetchone():
            print("Đã có tài khoản. Sử dụng API /v1/admin/staff để thêm nhân viên.", file=sys.stderr)
            return 1
    username = input("Tên quản trị viên mới: ").strip()
    password = getpass.getpass("Mật khẩu (ít nhất 12 ký tự): ")
    check = getpass.getpass("Xác nhận mật khẩu: ")
    if password != check:
        print("Mật khẩu không khớp", file=sys.stderr)
        return 1
    data = StaffCreate(username=username, password=password, role="ADMIN")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute("SELECT 1 FROM staff_users LIMIT 1").fetchone():
                print("Tài khoản đã được khởi tạo bởi phiên khác", file=sys.stderr)
                db.execute("ROLLBACK")
                return 1
            result = _create_staff(db, data)
            db.execute("COMMIT")
        except Exception:
            if db.in_transaction: db.execute("ROLLBACK")
            raise
    print("Đã tạo quản trị viên:", result["username"])
    print("Tiếp theo đặt COURTMATE_ALLOW_LEGACY_ADMIN=false khi chuyển hoàn toàn sang tài khoản cá nhân.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
