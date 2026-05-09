#include <SPI.h>
#include <RF24.h>

RF24 radio(4, 5);

const byte address[6] = "00001";

char message[32];

void setup() {
  Serial.begin(115200);

  if (!radio.begin()) {
    Serial.println("NRF not detected");
    while (1);
  }

  radio.openWritingPipe(address);

  radio.setPALevel(RF24_PA_LOW);

  radio.stopListening();

  Serial.println("Emergency Transmitter Ready");
  Serial.println("Send:");
  Serial.println("N = North/South emergency");
  Serial.println("E = East/West emergency");
}

void loop() {

  if (Serial.available()) {

    char cmd = Serial.read();

    if (cmd == 'N') {

      strcpy(message, "NS_EMERGENCY");

      radio.write(&message, sizeof(message));

      Serial.println("NS emergency sent");
    }

    if (cmd == 'E') {

      strcpy(message, "EW_EMERGENCY");

      radio.write(&message, sizeof(message));

      Serial.println("EW emergency sent");
    }
  }
}