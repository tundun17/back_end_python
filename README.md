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
{hashcode}/sensor    ESP -> Django: gui du lieu cam bien
{hashcode}/state     ESP -> Django: gui trang thai switch thuc te
{hashcode}/set       Django -> ESP: gui lenh bat/tat switch
```

Payload `syn`:

```json
{
  "hashcode": "ESP_ABC123",
  "esp_name": "ESP phong khach",
  "ip_address": "192.168.1.50",
  "firmware_version": "1.0.0"
}
```

Payload sensor:

```json
{
  "temperature": 31.5,
  "humidity": 72.0,
  "smoke_level": 420,
  "is_smoke_detected": false
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
  "success": true,
  "error_message": null
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
- `ActivityLog`: lich su thao tac user/he thong.

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
GET    /api/homes/{home_id}/rooms/
POST   /api/homes/{home_id}/rooms/
PATCH  /api/rooms/{id}/
DELETE /api/rooms/{id}/
```

### ESP

```text
GET    /api/devices/
POST   /api/devices/
GET    /api/devices/{id}/
PATCH  /api/devices/{id}/
DELETE /api/devices/{id}/
GET    /api/devices/{id}/status/
GET    /api/devices/{id}/mqtt-messages/
POST   /api/devices/{id}/mark-offline/
```

### Switch va dieu khien

```text
GET    /api/switches/
POST   /api/switches/
GET    /api/switches/{id}/
PATCH  /api/switches/{id}/
DELETE /api/switches/{id}/
POST   /api/switches/{id}/control/
GET    /api/switches/{id}/commands/
```

### Sensor, alert va dashboard

```text
GET   /api/devices/{id}/sensor-readings/latest/
GET   /api/devices/{id}/sensor-readings/history/
GET   /api/sensor-readings/
GET   /api/alerts/
GET   /api/alerts/{id}/
PATCH /api/alerts/{id}/resolve/
GET   /api/dashboard/overview/
GET   /api/dashboard/homes/{id}/overview/
GET   /api/dashboard/homes/{id}/analytics/
```

### Debug MQTT

```text
GET  /api/mqtt/messages/
GET  /api/mqtt/messages/{id}/
POST /api/mqtt/test-publish/
POST /api/debug/mqtt/inbound/
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
```

## Kiem thu khong can ESP

1. Tao `ESP` va `Switch` trong Django Admin.
2. Chay:

```bash
python manage.py mqtt_worker
```

3. Publish bang HiveMQ Web Client hoac MQTTX.

Topic:

```text
syn
```

Payload:

```json
{
  "hashcode": "ESP_ABC123",
  "esp_name": "ESP test"
}
```

Topic:

```text
ESP_ABC123/sensor
```

Payload:

```json
{
  "temperature": 50,
  "humidity": 70,
  "smoke_level": 900,
  "is_smoke_detected": true
}
```

Topic:

```text
ESP_ABC123/state
```

Payload:

```json
{
  "switch_code": "SWITCH_01",
  "actual_state": "ON",
  "success": true
}
```

Ket qua mong muon:

- `ESP.status = ONLINE`
- Tao `SensorReading`
- Tao `Alert` neu vuot nguong
- `Switch.actual_state = ON`
- Co log trong `MQTTMessage`

## Chuc nang noi bat

Chuc nang trong tam cua do an la dieu khien switch thong qua REST API ket hop MQTT state sync. Khi user bat/tat switch, backend tao command, publish MQTT xuong ESP, ghi log message va doi ESP publish state nguoc lai. Khi nhan state, MQTT worker cap nhat trang thai thuc te cua switch va trang thai command. Chuc nang nay the hien ro backend logic, database design, MQTT integration va kha nang kiem thu he thong.
