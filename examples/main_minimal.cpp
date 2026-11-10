// 最小自检 sketch + PSRAM 手动初始化参考（实测本机 YD-ESP32-S3 N8R2，2MB PSRAM 可用）。
// 不参与 PlatformIO 构建（src_dir = firmware/car）；要跑它就临时用它替换 firmware/car/car.ino。
#include <Arduino.h>
#include "esp_psram.h"
#include "esp_heap_caps.h"

// pioarduino 的 qio_qspi 变体开机不会自动初始化 PSRAM，需在应用层手动初始化并挂入堆。
// 注：esp_private/esp_psram_extram.h 的声明与 Arduino 头文件冲突，故手动声明所需函数。
extern "C" esp_err_t esp_psram_extram_add_to_heap_allocator(void);

void setup() {
  Serial.begin(115200);
  Serial.println("CarMaze ESP32-S3 ready");
  Serial.printf("Flash size: %u bytes\n", ESP.getFlashChipSize());
  Serial.printf("Free heap: %u bytes\n", ESP.getFreeHeap());

  if (!esp_psram_is_initialized()) {
    esp_psram_init();
  }
  if (esp_psram_get_size() > 0 && heap_caps_get_total_size(MALLOC_CAP_SPIRAM) == 0) {
    esp_psram_extram_add_to_heap_allocator();
  }

  Serial.printf("PSRAM size: %u bytes\n", heap_caps_get_total_size(MALLOC_CAP_SPIRAM));
}

void loop() {
  delay(1000);
}
