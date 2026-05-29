# Smart Home Backend Django MQTT

Backend cho he thong nha thong minh su dung Django REST Framework lam REST API server va MQTT de giao tiep voi ESP32. Dashboard, Swagger hoac Postman goi API den Django; ESP32 gui/nhan du lieu qua MQTT broker.

## Muc tieu

- Quan ly user, nha, phong, ESP va switch.
- Nhan du lieu cam bien nhiet do, do am, khoi qua MQTT.
- Dieu khien switch/relay tu REST API bang cach publish MQTT command.
- Dong bo trang thai thuc te cua switch khi ESP publish state.
- Luu lich su command, canh bao, MQTT message va activity log de de kiem thu va bao cao.

## Kien truc

```text
Dashboard / Postman / Swagger
        |
        | REST API + JWT
        v
Django REST Framework Backend
        |
        | Django ORM
        v
SQLite / MySQL / PostgreSQL

Django MQTT Worker <----> HiveMQ / MQTT Broker <----> ESP32
```

## MQTT topics

```text
syn                  ESP -> Django: bao online
{hashcode}/ack       Django -> ESP: xac nhan ESP da duoc chap nhan
{hashcode}/sensor    ESP -> Django: gui du lieu cam bien
{hashcode}/state     ESP -> Django: gui trang thai switch thuc te
{hashcode}/set       Django -> ESP: gui lenh bat/tat switch
```

Payload `syn`:

```json
{
  "hashcode": "ESP_ABC123",
  "ip_address": "192.168.1.50",
  "firmware_version": "1.0.0",
  "is_sensor": false,
  "num_switches": 2
}
```

Payload ACK sau khi backend xu ly `syn` thanh cong:

```json
{
  "hashcode": "ESP_ABC123",
  "ack": "OK"
}
```

Payload sensor:

```json
{
  "temperature": 31.5,
  "humidity": 72.0,
  "gas": 420
}
```

Payload command:

```json
{
  "command_id": 25,
  "command_type": "SET_DEVICE_STATE",
  "switch_code": "SWITCH_01",
  "state": "ON"
}
```

Payload state:

```json
{
  "command_id": 25,
  "switch_code": "SWITCH_01",
  "actual_state": "ON",
}
```

Voi cong tac vat ly, ESP co the gui state khong co `command_id`; backend van cap nhat `Switch.actual_state` va `Switch.sync_status`.

## Database chinh

- `Home`: nha cua user.
- `Room`: phong trong tung nha.
- `ESP`: ESP32, hashcode, phong, trang thai online/offline.
- `Switch`: switch/relay gan voi ESP, trang thai mong muon va trang thai thuc te.
- `SensorReading`: du lieu nhiet do, do am, muc khoi.
- `DeviceCommand`: lich su lenh backend publish xuong ESP.
- `Alert`: canh bao sensor hoac thiet bi.
- `MQTTMessage`: log MQTT inbound/outbound.

## REST API du kien

### Auth va user

```text
POST  /api/auth/register/
POST  /api/auth/login/
POST  /api/auth/refresh/
GET   /api/users/me/
PATCH /api/users/me/
POST  /api/users/change-password/
```

### Home va room

```text
GET    /api/homes/
POST   /api/homes/
GET    /api/homes/{id}/
PATCH  /api/homes/{id}/
DELETE /api/homes/{id}/
GET   /api//homes/{home_id}/overview/
GET    /api/homes/{home_id}/rooms/
POST   /api/homes/{home_id}/rooms/
PATCH  /api/rooms/{id}/
DELETE /api/rooms/{id}/
```

### ESP

```text
GET    /api/esps/
POST   /api/esps/
GET    /api/esps/{hashcode}/
PATCH  /api/esps/{hashcode}/
DELETE /api/esps/{hashcode}/
GET    /api/esps/{hashcode}/mqtt-messages/
```

### Switch va dieu khien

```text
GET    /api/esps/{hashcode}/switches/
GET    /api/esps/{hashcode}/switches/{switch_code}/
PATCH  /api/esps/{hashcode}/switches/{switch_code}/
POST   /api/esps/{hashcode}/switches/{switch_code}/control/
GET    /api/esps/{hashcode}/switches/{switch_code}/commands/
```

Payload control switch:

```json
{
  "state": "ON"
}
```

`state` chap nhan: `ON`, `OFF`, `1`, `0`, `true`, `false`.

### Sensor va alert

```text
GET   /api/esps/{hashcode}/sensor-readings/latest/
GET   /api/esps/{hashcode}/sensor-readings/history/
GET   /api/sensor-readings/
GET   /api/alerts/
GET   /api/alerts/{id}/
PATCH /api/alerts/{id}/resolve/
```

### Automation

```text
GET    /api/automation/
POST   /api/automation/
GET    /api/automation/{id}/
PATCH  /api/automation/{id}/
DELETE /api/automation/{id}/
```

Vi du tao rule: khi ESP sensor bao nhiet do cao thi bat quat o switch `device_1`.

```json
{
  "sensor_hashcode": "ESP_SENSOR_DEMO",
  "target_hashcode": "ESP_CONTROL_DEMO",
  "switch_code": "device_1",
  "alert_type": "HIGH_TEMPERATURE",
  "enabled": true,
  "active_state": "ON",
  "normal_state": "OFF"
}
```

Khi sensor vuot nguong, backend tu publish MQTT bat switch. Khi sensor tro lai binh thuong, backend resolve alert dang mo va publish MQTT dua switch ve `normal_state`.

### Debug MQTT

```text
GET  /api/mqtt/messages/
GET  /api/mqtt/messages/{id}/
POST /api/mqtt/test-publish/
```

## Chay project

Chay migration:

```bash
python manage.py migrate
```

Chay REST API server:

```bash
python manage.py runserver
```

Chay MQTT worker o terminal khac:

```bash
python manage.py mqtt_worker
```

Kiem tra ESP offline:

```bash
python manage.py health_check
```

Command nay se chay lien tuc. Mac dinh moi 1 phut check 1 lan. Neu ESP dang `ONLINE` nhung qua 10 phut khong gui MQTT len backend, command nay se chuyen ESP do sang `OFFLINE`.

## Cau hinh MQTT

Tao file `.env` tai thu muc project:

```text
MQTT_BROKER="your-hivemq-host"
MQTT_PORT=8883
MQTT_USERNAME="your-username"
MQTT_PASSWORD="your-password"
MQTT_TLS=True
MQTT_KEEPALIVE=60
MQTT_QOS=0
SMOKE_THRESHOLD=800
TEMPERATURE_THRESHOLD=45
HUMIDITY_THRESHOLD=80
ESP_OFFLINE_TIMEOUT_MINUTES=10
ESP_HEALTH_CHECK_INTERVAL_MINUTES=1
```

## Luong hoat dong hien tai

### 1. User dang ky va dang nhap

User tao tai khoan bang API:

```text
POST /api/auth/register/
```

Sau do dang nhap:

```text
POST /api/auth/login/
```

Backend tra ve JWT token gom `access` va `refresh`. Khi goi API can user, client gui them header:

```text
Authorization: Bearer <access_token>
```

Vi du xem thong tin user hien tai:

```text
GET /api/users/me/
```

### 2. Tao cau truc nha, phong va ESP

User tao nha:

```text
POST /api/homes/
```

Tao phong trong nha:

```text
POST /api/homes/{home_id}/rooms/
```

Tao ESP truoc trong backend:

```text
POST /api/esps/
```

Vi du ESP dieu khien switch:

```json
{
  "home_id": 1,
  "room_id": 1,
  "hashcode": "ESP_CONTROL_DEMO",
  "name": "ESP phong khach",
  "is_sensor": false
}
```

Luc nay backend da biet ESP nao hop le. Khi ESP that gui MQTT `syn`, backend se kiem tra `hashcode` co ton tai hay khong.

### 3. ESP ket noi MQTT va dong bo ban dau

Khi ESP ket noi HiveMQ, firmware gui `syn`:

```text
syn
```

Payload:

```json
{
  "hashcode": "ESP_CONTROL_DEMO",
  "ip_address": "192.168.1.50",
  "firmware_version": "1.0.0",
  "is_sensor": false,
  "num_switches": 2
}
```

Backend xu ly:

- Kiem tra `hashcode`.
- Cap nhat ESP thanh `ONLINE`.
- Luu `ip_address`, `firmware_version`, `last_seen_at`.
- Neu `is_sensor = false`, tu tao switch theo `num_switches`: `device_1`, `device_2`, ...
- Gui ACK xuong topic `{hashcode}/ack`.

Payload ACK:

```json
{
  "hashcode": "ESP_CONTROL_DEMO",
  "ack": "OK"
}
```

Khi ESP nhan duoc ACK OK, ESP bat dau hoat dong binh thuong.

### 4. Dieu khien switch tu API

Frontend hoac Postman goi:

```text
POST /api/esps/{hashcode}/switches/{switch_code}/control/
```

Payload:

```json
{
  "state": "ON"
}
```

Backend se:

- Tim ESP va switch.
- Tao `DeviceCommand`.
- Publish MQTT xuong topic `{hashcode}/set`.
- Cap nhat switch thanh `desired_state = ON`, `sync_status = PENDING`.

Payload MQTT gui xuong ESP:

```json
{
  "command_id": 1,
  "command_type": "SET_DEVICE_STATE",
  "switch_code": "device_1",
  "state": "ON"
}
```

ESP nhan lenh, bat/tat relay that, roi gui state nguoc lai:

```text
{hashcode}/state
```

Payload:

```json
{
  "command_id": 1,
  "switch_code": "device_1",
  "actual_state": "ON",
  "success": true
}
```

Backend cap nhat:

- `Switch.actual_state = ON`
- `Switch.desired_state = ON`
- `Switch.sync_status = SYNCED`
- `DeviceCommand.status = DONE`

Neu user bam cong tac vat ly, ESP van gui state len MQTT nhung co the khong co `command_id`. Khi do backend cap nhat ca `actual_state` va `desired_state` theo trang thai that de tranh lech du lieu.

### 5. ESP sensor gui du lieu

ESP sensor gui len topic:

```text
{hashcode}/sensor
```

Payload:

```json
{
  "temperature": 31.5,
  "humidity": 70,
  "gas": 420
}
```

Backend se:

- Luu vao `SensorReading`.
- Cap nhat `last_seen_at` cua ESP.
- Tao `Alert` neu gas hoac nhiet do vuot nguong cau hinh.
- Goi automation engine de kiem tra co rule phu hop hay khong.

Frontend co the doc du lieu sensor qua:

```text
GET /api/esps/{hashcode}/sensor-readings/latest/
GET /api/esps/{hashcode}/sensor-readings/history/
```

### 6. Automation xu ly rule tu dong

User co the tao automation rule bang API:

```text
POST /api/automation/
```

Vi du: khi ESP sensor bao nhiet do cao thi bat switch `device_1` cua ESP dieu khien quat.

```json
{
  "sensor_hashcode": "ESP_SENSOR_DEMO",
  "target_hashcode": "ESP_CONTROL_DEMO",
  "switch_code": "device_1",
  "alert_type": "HIGH_TEMPERATURE",
  "enabled": true,
  "active_state": "ON",
  "normal_state": "OFF"
}
```

Khi sensor gui du lieu vuot nguong, backend tao hoac cap nhat alert dang mo. Sau do automation engine se:

- Tim rule dang bat `enabled = true` theo sensor ESP va `alert_type`.
- Tim switch muc tieu can dieu khien.
- Publish MQTT command xuong topic `{target_hashcode}/set`.
- Cap nhat `desired_state` cua switch thanh `active_state`.

Khi du lieu sensor tro lai muc binh thuong, backend se resolve alert dang mo. Neu automation rule co `normal_state`, backend publish command dua switch ve trang thai binh thuong, vi du tat quat khi nhiet do da giam.

Frontend co the quan ly automation qua:

```text
GET    /api/automation/
GET    /api/automation/{id}/
PATCH  /api/automation/{id}/
DELETE /api/automation/{id}/
```

### 7. Dashboard doc du lieu tong quan

Dashboard goi:

```text
GET /api/homes/{home_id}/overview/
```

API nay gom so lieu:

- Tong so phong.
- Tong so ESP.
- ESP online/offline/unclaimed/error.
- So ESP sensor/controller.
- So switch ON/OFF.
- So switch `PENDING`, `FAILED`, `SYNCED`.
- So alert dang ton tai.

Dashboard co the goi them cac API rooms, esps, switches, sensor readings va mqtt messages de hien thi chi tiet.

### 8. Health check danh dau ESP offline

Neu ESP khong gui MQTT len backend qua thoi gian cau hinh, chay:

```bash
python manage.py health_check
```

Command nay se chay lien tuc. Mac dinh moi 1 phut check 1 lan. Neu ESP dang `ONLINE` nhung qua 10 phut khong cap nhat `last_seen_at`, backend chuyen ESP do sang `OFFLINE`.

## Chuc nang noi bat

Chuc nang trong tam cua do an la dieu khien switch thong qua REST API ket hop MQTT state sync. Khi user bat/tat switch, backend tao command, publish MQTT xuong ESP, ghi log message va doi ESP publish state nguoc lai. Khi nhan state, MQTT worker cap nhat trang thai thuc te cua switch va trang thai command. Chuc nang nay the hien ro backend logic, database design, MQTT integration va kha nang kiem thu he thong.
