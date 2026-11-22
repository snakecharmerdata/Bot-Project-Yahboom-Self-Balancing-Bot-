#include <WiFi.h>
#include "wifi_secrets.h"

namespace {

constexpr uint32_t LIDAR_BAUD = 230400;
constexpr int LIDAR_RX_PIN = 16;
constexpr int LIDAR_TX_PIN = 17;
constexpr uint16_t BRIDGE_PORT = 8888;

WiFiServer server(BRIDGE_PORT);

void connectToWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Wi-Fi connected. IP: ");
  Serial.println(WiFi.localIP());
}

void relayClient(WiFiClient &client) {
  uint8_t buffer[256];
  client.setNoDelay(true);

  Serial.print("App connected from ");
  Serial.println(client.remoteIP());

  while (client.connected()) {
    int count = Serial2.available();
    if (count > 0) {
      if (count > static_cast<int>(sizeof(buffer))) {
        count = sizeof(buffer);
      }
      const size_t received = Serial2.read(buffer, count);
      if (received > 0) {
        client.write(buffer, received);
      }
    }

    count = client.available();
    if (count > 0) {
      if (count > static_cast<int>(sizeof(buffer))) {
        count = sizeof(buffer);
      }
      const size_t received = client.read(buffer, count);
      if (received > 0) {
        Serial2.write(buffer, received);
      }
    }
    delay(1);
  }

  client.stop();
  Serial.println("App disconnected");
}

}  // namespace

void setup() {
  Serial.begin(115200);
  Serial2.begin(LIDAR_BAUD, SERIAL_8N1, LIDAR_RX_PIN, LIDAR_TX_PIN);
  connectToWiFi();
  server.begin();
  Serial.printf("Raw LiDAR TCP bridge listening on port %u\n", BRIDGE_PORT);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected; reconnecting");
    WiFi.reconnect();
    delay(1000);
    return;
  }

  WiFiClient client = server.accept();
  if (client) {
    relayClient(client);
  }
  delay(1);
}
