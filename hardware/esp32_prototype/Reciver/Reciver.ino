#include <SPI.h>
#include <RF24.h>

RF24 radio(4, 5);

const byte address[6] = "00001";

char text[32] = "";

// LED Pins
#define NR 13
#define NG 12

#define SR 14
#define SG 27

#define ER 26
#define EG 25

#define WR 33
#define WG 32

unsigned long lastSwitch = 0;

bool nsGreen = true;

void setup() {

  Serial.begin(115200);

  pinMode(NR, OUTPUT);
  pinMode(NG, OUTPUT);

  pinMode(SR, OUTPUT);
  pinMode(SG, OUTPUT);

  pinMode(ER, OUTPUT);
  pinMode(EG, OUTPUT);

  pinMode(WR, OUTPUT);
  pinMode(WG, OUTPUT);

  if (!radio.begin()) {
    Serial.println("NRF not detected");
    while (1);
  }

  radio.openReadingPipe(0, address);

  radio.setPALevel(RF24_PA_LOW);

  radio.startListening();

  setNSGreen();

  lastSwitch = millis();
}

void loop() {

  // Check for emergency signal
  if (radio.available()) {

    radio.read(&text, sizeof(text));

    Serial.print("Received: ");
    Serial.println(text);

    if (strcmp(text, "NS_EMERGENCY") == 0) {

      setNSGreen();

      nsGreen = true;

      lastSwitch = millis();

      Serial.println("Emergency -> NS GREEN");
    }

    if (strcmp(text, "EW_EMERGENCY") == 0) {

      setEWGreen();

      nsGreen = false;

      lastSwitch = millis();

      Serial.println("Emergency -> EW GREEN");
    }
  }

  // Automatic switching every 120 seconds
  if (millis() - lastSwitch >= 120000) {

    if (nsGreen) {

      setEWGreen();

      nsGreen = false;

      Serial.println("Switched to EW GREEN");
    }

    else {

      setNSGreen();

      nsGreen = true;

      Serial.println("Switched to NS GREEN");
    }

    lastSwitch = millis();
  }
}

void setNSGreen() {

  // NS Green
  digitalWrite(NG, HIGH);
  digitalWrite(SG, HIGH);

  digitalWrite(NR, LOW);
  digitalWrite(SR, LOW);

  // EW Red
  digitalWrite(ER, HIGH);
  digitalWrite(WR, HIGH);

  digitalWrite(EG, LOW);
  digitalWrite(WG, LOW);
}

void setEWGreen() {

  // EW Green
  digitalWrite(EG, HIGH);
  digitalWrite(WG, HIGH);

  digitalWrite(ER, LOW);
  digitalWrite(WR, LOW);

  // NS Red
  digitalWrite(NR, HIGH);
  digitalWrite(SR, HIGH);

  digitalWrite(NG, LOW);
  digitalWrite(SG, LOW);
}