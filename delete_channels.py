import sys
import argparse
import mariadb

from fabric import Connection, Config

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--username", type=str, required=True, help="Username")
    parser.add_argument("-p", "--password", type=str, required=True, help="Password")
    return parser.parse_args()

def init_database_connection(database):
    try:
        conn = mariadb.connect(
                database=database,
                user="",
                password="",
                host="",
                port=3306
        )
    except mariadb.Error as e:
        print(f"[!] {e}")
        sys.exit(1)
    return conn

def main():
    args = parse_args()
    username = args.username
    password = args.password

    with open("ext_ids") as file: # IT ACCEPTS EXT_ID ONLY, DO NOT PUSH ANY OTHER INFO HERE
        deleted = 0
        total = 0
        conn = init_database_connection("cctv_b2c")
        config = Config(overrides={'sudo': {'password': password}, 'connect_kwargs': {'password': password}})
        ssh_conn = Connection(f"{username}@172.0.10.2", config=config)
        for ext_id in file:
            ext_id = ext_id.rstrip()
            total += 1
            cur = conn.cursor() 

            cur.execute(f"select cam.id, cam.channel_id from cctv_b2c.camera cam where cam.ext_id like '%{ext_id}%'")
            info = cur.fetchone() # tuple (id, channel_id)

            if not info:
                print(f"[!] Entry {ext_id} not found")
                continue

            print(f"[~] Deleting {ext_id} on VS")

            response = ssh_conn.run(f"sudo docker exec cctv-video--kzt-cvs-srv26 curl -s http://operator:operator@localhost:8080/channels/delete/{info[1]} | jq .", hide=True)
            if "404," in response.stdout:
                print(f"[!] Couldn't delete {ext_id} on VS")

            print(f"[~] Deleting {ext_id} in database")

            cur.close()
            cur = conn.cursor() 

            cur.execute(f"""   
                delete from cctv_b2c.camera_creator where camera_id = '{info[0]}';
                delete from cctv_b2c.kztb2b_admin_slaves_camera where camera_id = '{info[0]}';
                delete from cctv_b2c.camera_url where camera_id = '{info[0]}';
                delete from cctv_b2c.b2b_user_camera_permission where camera_id = '{info[0]}';
                delete from cctv_b2c.echd_camera_group_camera where camera_id = '{info[0]}';
                delete from cctv_b2c.company_camera where camera_id = '{info[0]}';
                delete from cctv_b2c.user_archive where camera_id = '{info[0]}';
                delete from cctv_b2c.camera where id = '{info[0]}';
            """)

            cur.close()
            
            deleted += 1
            print(f"[~] Deleted {ext_id}")
        conn.commit()
        conn.close()
        print(f"[-] Deleted {deleted} channels out of {total}")

if __name__ == "__main__":
    main()