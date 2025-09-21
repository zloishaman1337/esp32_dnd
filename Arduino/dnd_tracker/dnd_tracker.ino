// ESP32-S3 DnD Initiative tracker — simplified
#include <lvgl.h>
#include <Arduino_GFX_Library.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include <Wire.h>

/* ------------------ Display pins (оставь свои) ------------------ */
#define LCD_SCLK 39
#define LCD_MOSI 38
#define LCD_MISO 40
#define LCD_DC 42
#define LCD_RST -1
#define LCD_CS 45
#define LCD_BL 1
#define TP_SDA 48
#define TP_SCL 47

#define LEDC_FREQ             5000
#define LEDC_TIMER_10_BIT     10

#define LCD_ROTATION 0
#define LCD_H_RES 240
#define LCD_V_RES 320

/* ------------------ WiFi: вставь свои данные ------------------ */
const char* WIFI_SSID = "Shamanchik13372g";
const char* WIFI_PASS = "37032005";

/* ------------------ TCP server ------------------ */
const uint16_t SERVER_PORT = 5000;
WiFiServer tcpServer(SERVER_PORT);
WiFiClient client;

/* ------------------ GFX (как в твоём скетче) ------------------ */
Arduino_DataBus *bus = new Arduino_ESP32SPI(
  LCD_DC, LCD_CS,
  LCD_SCLK, LCD_MOSI, LCD_MISO);

Arduino_GFX *gfx = new Arduino_ST7789(
  bus, LCD_RST, LCD_ROTATION, true,
  LCD_H_RES, LCD_V_RES);

uint32_t screenWidth;
uint32_t screenHeight;
uint32_t bufSize;
lv_disp_draw_buf_t draw_buf;
lv_color_t *disp_draw_buf;
lv_disp_drv_t disp_drv;

/* ------------------ LVGL objects ------------------ */
lv_obj_t *label_title;
lv_obj_t *label_current;
lv_obj_t *label_details;
lv_style_t style_player;
lv_style_t style_enemy;
lv_style_t style_big;

/* ------------------ Players storage ------------------ */
struct Player {
  String name;
  String klass;
  int hp;
  int cd;
  int init;
};
#define MAX_PLAYERS 16
Player players[MAX_PLAYERS];
int players_count = 0;
int current_index = 0;
bool battle_active = false;

/* ------------------ Helpers ------------------ */
void clear_players() {
  for (int i=0;i<MAX_PLAYERS;i++){
    players[i].name = "";
    players[i].klass = "";
    players[i].hp = 0;
    players[i].cd = 0;
    players[i].init = 0;
  }
  players_count = 0;
  current_index = 0;
  battle_active = false;
}

void update_display() {
  // Обновляем LVGL метки
  String title = "DnD Initiative";
  lv_label_set_text(label_title, title.c_str());

  if (players_count == 0) {
    lv_label_set_text(label_current, "No players");
    lv_label_set_text(label_details, "");
    return;
  }

  if (!battle_active) {
    String s = "Ready. Players: " + String(players_count);
    lv_label_set_text(label_current, s.c_str());
    lv_label_set_text(label_details, "Press start from host");
    return;
  }

  if (current_index < 0 || current_index >= players_count) current_index = 0;
  Player &p = players[current_index];

  String cur = String(current_index+1) + ". " + p.name + " (" + p.klass + ")";
  lv_label_set_text(label_current, cur.c_str());

  String det = "HP: " + String(p.hp) + "  CD: " + String(p.cd) + "  Init: " + String(p.init);
  lv_label_set_text(label_details, det.c_str());

  // Цвет: враг = красный, игрок = белый
  if (p.klass == "Enemy") {
    lv_obj_add_style(label_current, &style_enemy, 0);
    lv_obj_add_style(label_details, &style_enemy, 0);
  } else {
    lv_obj_add_style(label_current, &style_player, 0);
    lv_obj_add_style(label_details, &style_player, 0);
  }
}

/* ------------------ LVGL UI init ------------------ */
void lv_ui_init() {
  lv_obj_t *scr = lv_scr_act();
  lv_obj_clean(scr);
  lv_style_init(&style_player);
  lv_style_set_text_color(&style_player, lv_color_black());

  lv_style_init(&style_enemy);
  lv_style_set_text_color(&style_enemy, lv_color_hex(0xFF0000)); // красный

  lv_style_init(&style_big);
  lv_style_set_text_font(&style_big, &lv_font_montserrat_28); // большой шрифт
  label_title = lv_label_create(scr);
  lv_label_set_text(label_title, "");
  lv_obj_align(label_title, LV_ALIGN_TOP_MID, 0, 8);

  label_current = lv_label_create(scr);
  lv_label_set_text(label_current, "");
  lv_obj_add_style(label_current, &style_big, 0);
  lv_obj_align(label_current, LV_ALIGN_CENTER, 0, -40);

  label_details = lv_label_create(scr);
  lv_label_set_text(label_details, "");
  lv_obj_add_style(label_details, &style_big, 0);
  lv_obj_align(label_details, LV_ALIGN_CENTER, 0, 40);

  update_display();
}

/* ------------------ TCP/JSON protocol ------------------
Expected JSON messages (examples):
1) init_players:
{"cmd":"init_players","players":[{"name":"Bob","class":"Fighter","hp":30,"cd":0,"init":15}, ...]}

2) start_battle:
{"cmd":"start_battle","order":[0,1,2]}  // optional order, otherwise order by provided list

3) next_turn:
{"cmd":"next_turn"}

4) set_current:
{"cmd":"set_current","index":2}
------------------------------------------------------------------ */

void handle_init_players(JsonArray arr) {
  clear_players();
  int i = 0;
  for (JsonObject obj : arr) {
    if (i >= MAX_PLAYERS) break;
    players[i].name = String((const char*)obj["name"]);
    players[i].klass = String((const char*)obj["class"]);
    players[i].hp = obj["hp"] | 0;
    players[i].cd = obj["cd"] | 0;
    players[i].init = obj["init"] | 0;
    i++;
  }
  players_count = i;
  battle_active = false;
  current_index = 0;
  update_display();
}

void handle_stop_battle() {
  clear_players();
  players_count = 0;
  battle_active = false;
  current_index = 0;
  update_display();
}

void handle_start_battle(JsonArray order) {
  // если передан порядок — переставим массив
  if (order) {
    // создаём временный массив и сортируем по переданному порядку
    Player tmp[MAX_PLAYERS];
    int new_count = 0;
    for (JsonVariant v : order) {
      int idx = v.as<int>();
      if (idx >=0 && idx < players_count) {
        tmp[new_count++] = players[idx];
      }
    }
    // если порядок пустой или неполный — дополним оставшимися
    for (int i=0;i<players_count;i++){
      bool found = false;
      for (int j=0;j<new_count;j++){
        if (tmp[j].name == players[i].name) { found=true; break; }
      }
      if (!found) tmp[new_count++] = players[i];
    }
    // копируем назад
    for (int i=0;i<new_count;i++) players[i] = tmp[i];
    players_count = new_count;
  }
  battle_active = true;
  current_index = 0;
  update_display();
}

void handle_next_turn() {
  if (!battle_active || players_count==0) return;
  current_index++;
  if (current_index >= players_count) current_index = 0;
  update_display();
}

void handle_set_current(int idx) {
  if (idx >= 0 && idx < players_count) {
    current_index = idx;
    update_display();
  }
}

void process_json(const String &json) {
  StaticJsonDocument<2048> doc; // при необходимости увеличить
  DeserializationError err = deserializeJson(doc, json);
  if (err) {
    Serial.print("JSON parse error: ");
    Serial.println(err.c_str());
    return;
  }
  const char* cmd = doc["cmd"];
  if (!cmd) return;
  if (strcmp(cmd, "init_players") == 0) {
    JsonArray arr = doc["players"].as<JsonArray>();
    if (arr) handle_init_players(arr);
    else Serial.println("init_players missing players array");
  } else if (strcmp(cmd, "start_battle") == 0) {
    JsonArray order = doc["order"].as<JsonArray>();
    handle_start_battle(order);
  } else if (strcmp(cmd, "next_turn") == 0) {
    handle_next_turn();
  } else if (strcmp(cmd, "set_current") == 0) {
    int idx = doc["index"] | -1;
    handle_set_current(idx);
  } 
  else if (strcmp(cmd, "stop_battle") == 0) {
    handle_stop_battle();
  }
  else {
    Serial.print("Unknown cmd: "); Serial.println(cmd);
  }
}

/* ------------------ Setup/Loop ------------------ */
void setup() {
  Serial.begin(115200);
  delay(100);

  if (!gfx->begin()) {
    Serial.println("gfx->begin() failed!");
  }
  gfx->fillScreen(BLACK);

#ifdef LCD_BL
  ledcAttach(LCD_BL, LEDC_FREQ, LEDC_TIMER_10_BIT);
  ledcWrite(LCD_BL, (1 << LEDC_TIMER_10_BIT) / 100 * 80);
#endif

  // I2C (если нужно)
  Wire.begin(TP_SDA, TP_SCL);

  // WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi failed");
  } else {
    Serial.println("\nWiFi connected");
    Serial.print("IP: "); Serial.println(WiFi.localIP());
  }

  // LVGL init
  lv_init();
  screenWidth = gfx->width();
  screenHeight = gfx->height();
  bufSize = screenWidth * screenHeight;
  disp_draw_buf = (lv_color_t *)heap_caps_malloc(bufSize * 2, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
  if (!disp_draw_buf) {
    disp_draw_buf = (lv_color_t *)heap_caps_malloc(bufSize * 2, MALLOC_CAP_8BIT);
  }
  if (!disp_draw_buf) {
    Serial.println("LVGL buffer alloc failed!");
  } else {
    lv_disp_draw_buf_init(&draw_buf, disp_draw_buf, NULL, bufSize);
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = screenWidth;
    disp_drv.ver_res = screenHeight;
    // минимальный flush — мы просто пометим готовность, фактическая отрисовка в loop()
    disp_drv.flush_cb = [](lv_disp_drv_t *disp_drv, const lv_area_t *area, lv_color_t *color_p){
      lv_disp_flush_ready(disp_drv);
    };
    disp_drv.draw_buf = &draw_buf;
    disp_drv.direct_mode = true;
    lv_disp_drv_register(&disp_drv);
    lv_ui_init();
  }

  // TCP server
  tcpServer.begin();
  tcpServer.setNoDelay(true);
  Serial.printf("TCP server started on port %u\n", SERVER_PORT);
  clear_players();
  update_display();
}

String recv_buffer = "";

void loop() {
  // LVGL handler
  lv_timer_handler();
  // draw LVGL buffer to screen
#if (LV_COLOR_16_SWAP != 0)
  gfx->draw16bitBeRGBBitmap(0, 0, (uint16_t *)disp_draw_buf, screenWidth, screenHeight);
#else
  gfx->draw16bitRGBBitmap(0, 0, (uint16_t *)disp_draw_buf, screenWidth, screenHeight);
#endif

  // Accept client if none
  if (!client || !client.connected()) {
    if (client) client.stop();
    client = tcpServer.available();
    if (client) {
      Serial.println("Client connected");
      recv_buffer = "";
    }
  } else {
    // Read available data
    while (client.available()) {
      String line = client.readStringUntil('\n'); // messages must end with '\n'
      line.trim();
      if (line.length() == 0) continue;
      // Если пришло несколько частей — аккумулируем
      recv_buffer += line;
      // Попробуем распарсить — предполагаем полный JSON в recv_buffer
      // Для простоты — если начинается с '{' и заканчивается '}', считаем готовым
      int first = recv_buffer.indexOf('{');
      int last = recv_buffer.lastIndexOf('}');
      if (first != -1 && last != -1 && last > first) {
        String json = recv_buffer.substring(first, last+1);
        Serial.print("Received JSON: "); Serial.println(json);
        process_json(json);
        // удалим обработанную часть
        if (last+1 < (int)recv_buffer.length()) recv_buffer = recv_buffer.substring(last+1);
        else recv_buffer = "";
      } else {
        // ждём продолжения
      }
    }
  }

  delay(20);
}
