# Context 3 server Prod — Odoo Billing (v2, nền hoàn tất)

> File import sang chat khác. Ảnh chụp trạng thái tại thời điểm cập nhật.
> Cập nhật: 2026-10-26 (chiều)

---

## 0. Tổng quan — NỀN CẢ 3 SERVER ĐÃ XONG

| Server | IP | Vai trò | Nền |
|---|---|---|---|
| CICD | 172.24.52.11 | GitLab + Runner | ✅ GitLab chạy, Runner đăng ký, Variables khai |
| APP | 172.24.52.10 | Odoo + PostgreSQL primary | ✅ disk + Docker + Harbor + 6 image nền |
| DATA | 172.24.52.140 | Replica + DWH + Airflow + giám sát | ✅ disk + Docker + Harbor + 8 image nền |

Mapping IP đã chốt: **.10=APP, .11=CICD, .140=DATA**.

---

## 1. Harbor (registry dùng chung) — QUAN TRỌNG

- Host `vcr.vnpost.vn` · project `logistics-vnpl-esd` · account `vnpl_cicd` (login OK từ cả 3 server).
- Server KHÔNG ra Docker Hub → mọi image kéo từ Harbor.
- **Namespace lẫn lộn** (lưu ý khi viết compose): hầu hết phẳng, nhưng vài image giữ tầng gốc:
  - `gitlab/gitlab-ce:19.4.3-ce.0` (có tầng `gitlab/`)
  - `apache/airflow:2.10.3` (có tầng `apache/`)
  - Phẳng: `odoo:19.0`, `postgres:17`, `nginx:1.27-alpine`, `grafana:11.3.0`, `prometheus:v3.0.1`, `loki:3.2.1`, `node-exporter:v1.8.2`, `postgres-exporter:v0.16.0`, `gitlab-runner:v19.4.0`, `docker:27`, `docker:27-dind`.
  - Liệt kê thật: `curl -s -u vnpl_cicd "https://vcr.vnpost.vn/v2/_catalog?n=200"`.
- Kéo image lớn đôi khi `connection reset by peer` giữa chừng → retry (pull có resume), vài lần là xong.

---

## 2. CICD .11 — GitLab

- GitLab CE `gitlab/gitlab-ce:19.4.3-ce.0` + Runner `gitlab-runner:v19.4.0`, chạy bằng docker compose tại `/data/gitlab/docker-compose.yml`.
- Registry built-in của GitLab **TẮT** (dùng Harbor). HTTP tạm (chưa cert).
- Nghe `172.24.52.11:80` + git-SSH `2222`. Publish qua **LB** → `git.vietnampostlogistics.com`.
- Runner đăng ký tag `cicd`, executor docker, dind, privileged. (Kiểm: `docker exec gitlab-runner grep -E 'privileged|image' /etc/gitlab-runner/config.toml`.)
- Project: group `vnpl_esd`, repo `vnpl_billing`. CI/CD Variables đã khai: `HARBOR_USER`, `HARBOR_PASSWORD` (masked+protected).
- Docker: Community 29.9.2 (từ download.docker.com). Ổ Data `/data` 246G (vdb).

---

## 3. APP .10 — Odoo

- Docker: `docker.io` kho Ubuntu. Ổ Data `/data` 147G (vdb).
- Image nền đã kéo: `odoo:19.0`, `postgres:17`, `nginx:1.27-alpine`, `node-exporter`, `postgres-exporter`, `alloy:v1.5.0`.
- Thư mục dữ liệu: `/data/odoo/{config,filestore}`, `/data/postgresql`.
- **Chờ**: image `vnpl-billing` do CI build; file `.env` + `odoo.conf` thật (secret) + compose prod.

---

## 4. DATA .140 — gotcha về ổ đĩa (ĐỌC KỸ)

- Ổ OS ban đầu **chỉ 11G** (sai hồ sơ 50G). LVM còn 10.97G trống → đã `lvextend +100%FREE` + `resize2fs` → `/` lên **~22G**. Vẫn thiếu so với hồ sơ, **cần hạ tầng cấp thêm OS** (đã nêu, chờ).
- Docker mới dùng **containerd image store**: `data-root` của Docker KHÔNG gom image. Phải chuyển **containerd** sang /data:
  - `/etc/docker/daemon.json`: `{ "data-root": "/data/docker" }`
  - `/etc/containerd/config.toml`: `root = '/data/containerd'` (file dùng **nháy đơn**).
  - Đã verify: kéo postgres → `/data/containerd` phình, `/var/lib/containerd` giữ 37M. ✅
- Ổ Data `/data` 442G (vdb). Ổ OS sau khi kéo hết image vẫn 36% (an toàn).
- Image nền đã kéo (8): `postgres:17`, `apache/airflow:2.10.3`, `grafana:11.3.0`, `prometheus:v3.0.1`, `loki:3.2.1`, `nginx:1.27-alpine`, `node-exporter`, `postgres-exporter`.
- Thư mục dữ liệu: `/data/{postgresql,airflow,grafana,prometheus,loki}`. `grafana` đã `chown 472:472`.
- Dọn: `/var/lib/containerd.old` còn chờ xóa sau khi chạy ổn.

---

## 5. Proxy / mạng

- Squid `172.24.19.11:8080` (user/pass `proxy08/proxy08`).
- **Rule proxy có thời hạn** — apt từng bị `403` (hết hạn), đã nhờ mở lại cho cả 3 IP. Nên hỏi hạ tầng để **thường trực** giai đoạn cài đặt.
- `no_proxy` phải liệt kê IP cụ thể (3 server + Harbor `172.24.19.11` + `.vnpost.vn` + `.vietnampostlogistics.com`); công cụ KHÔNG hiểu CIDR.
- **PyPI**: tunnel TCP mở nhưng **TLS bị cắt** (`SSL_ERROR_SYSCALL` sau Client hello) — đã gửi log, chờ hạ tầng xử SSL-bump/SNI. Chỉ cần khi build có `pip install`.

---

## 6. Truy cập & publish

- Server chỉ nhận SSH qua **PAM** (`pam-partner.vnpost.vn`, Guacamole). VPN KHÔNG đi thẳng tới `172.24.52.x`. PAM không truyền file.
- Máy cá nhân KHÔNG nối thẳng production. Dịch vụ publish đi qua **LB** (hoặc VDI trung gian). GitLab đã publish qua LB.
- **DNS nội bộ** `git.vietnampostlogistics.com` → cần ticket QTHT khai (đang test, chưa khai chính thức). Máy dev bị khóa quyền sửa hosts → phụ thuộc DNS.
- NTP: cả 3 server `synchronized: no` (giờ vẫn đúng nhờ RTC). Cần **NTP nội bộ** từ hạ tầng.

---

## 7. Pipeline (khi có code)

- Repo dev hiện mount addon → phải chuyển build image: thêm Dockerfile (`FROM vcr.vnpost.vn/logistics-vnpl-esd/odoo:19.0`), `.gitlab-ci.yml`, requirements, .gitignore, .dockerignore. (Chi tiết ở guide `20261026_cicd_repo_prod_guide.md`.)
- Build trên `.11` (dind) → push `vnpl-billing:<sha>` lên Harbor → APP pull.
- Proxy phải truyền vào build qua `--build-arg` (pip/apt trong image); Harbor không đi proxy (NO_PROXY).

---

## 8. Việc còn tồn

- [ ] **Máy dev**: push code lên `vnpl_esd/vnpl_billing` → kích hoạt CI.
- [ ] Thêm Dockerfile + `.gitlab-ci.yml` vào repo (chuyển dev→prod).
- [ ] Chạy pipeline build đầu tiên (branch `main` vì Variables protected).
- [ ] Dựng stack: APP (Odoo+PG), DATA (replica+airflow+giám sát) — cần compose + secret.
- [ ] Runner shell trên APP (tag `app-shell`) cho deploy stage.
- [ ] **Hạ tầng**: PyPI TLS; DNS nội bộ 4 subdomain; NTP nội bộ; cấp thêm OS cho .140; proxy thường trực.
- [ ] Postgres replication: primary (APP) → replica (DATA) bằng `pg_basebackup`.
- [ ] GitLab HTTP→HTTPS khi có cert/DNS.
- [ ] Web GitLab: tắt sign-up (Deactivate), dùng tài khoản thường thay root.
