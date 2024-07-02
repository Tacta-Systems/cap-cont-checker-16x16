const int addrPinRow[] = {36,38,40,42}; // LSB first
const int addrPinCol[] = {37,39,41,43};
const int addrPinRst[] = {44,46,48,50};

const int COL_MUX_EN = 45;
const int RST_MUX_EN = 47;
const int ROW_MUX_EN = 49;

const int N_ROW_DEC_EN = 51;
const int N_ROW_MODE_SEL = 53;

const int DELAY_TIME = 10;

void setup() {
  for (int i=0;i<4;i++)
  {
    pinMode(addrPinRow[i], OUTPUT);
  }
  for (int i=0;i<4;i++)
  {
    pinMode(addrPinCol[i], OUTPUT);
  }
  for (int i=0;i<4;i++)
  {
    pinMode(addrPinRst[i], OUTPUT);
  }
  pinMode(COL_MUX_EN, OUTPUT);
  pinMode(RST_MUX_EN, OUTPUT);
  pinMode(ROW_MUX_EN, OUTPUT);
  pinMode(N_ROW_DEC_EN, OUTPUT);
  pinMode(N_ROW_MODE_SEL, OUTPUT);
  digitalWrite(N_ROW_MODE_SEL, LOW);
  digitalWrite(N_ROW_DEC_EN, LOW);
  digitalWrite(ROW_MUX_EN, LOW);
  digitalWrite(COL_MUX_EN, LOW);
  digitalWrite(RST_MUX_EN, LOW);
  Serial.begin(9600);
}

char state = ' ';
/*
States:
the reason we're using these names is because we're limited to one character + can't use the letters 'A' - 'F'.
- 'O' for continuity check mode
- 'P' for capacitance check mode
- 'S' for reset sweep mode
- 'R' for writing to the row muxes
- 'L' for writing to the column muxes
- 'T' for writing to the reset muxes
*/

void loop() {
  char cmd;
  if (Serial.available() > 0) {
    cmd = Serial.read();
  }
  if (cmd == 'O') { // continuity check mode
    state = 'O';
    digitalWrite(N_ROW_MODE_SEL, HIGH);
    digitalWrite(N_ROW_DEC_EN, HIGH);
    digitalWrite(ROW_MUX_EN, HIGH);
    digitalWrite(COL_MUX_EN, HIGH);
    digitalWrite(RST_MUX_EN, LOW);
    displayBinaryRow(0);
    displayBinaryCol(0);
    displayBinaryRst(0);
  }
  else if (cmd == 'P') { // capacitance checker mode
    state = 'P';
    digitalWrite(N_ROW_MODE_SEL, LOW);
    digitalWrite(N_ROW_DEC_EN, LOW);
    digitalWrite(ROW_MUX_EN, HIGH);
    digitalWrite(COL_MUX_EN, HIGH);
    digitalWrite(RST_MUX_EN, LOW);
    displayBinaryRow(0);
    displayBinaryCol(0);
    displayBinaryRst(0);
  }
  else if (cmd == 'S') { // reset sweep mode
    state = 'S';
    digitalWrite(N_ROW_MODE_SEL, LOW);
    digitalWrite(N_ROW_DEC_EN, LOW);
    digitalWrite(ROW_MUX_EN, LOW);
    digitalWrite(COL_MUX_EN, LOW);
    digitalWrite(RST_MUX_EN, HIGH);
    displayBinaryRow(0);
    displayBinaryCol(0);
    displayBinaryRst(0);
  }
  else if (cmd == 'R') {
    state = 'R';
    displayBinaryRow(0);
  }
  else if (cmd == 'L') {
    state = 'L';
    displayBinaryCol(0);
  }
  else if (cmd == 'T') {
    state = 'T';
    displayBinaryRst(0);
  }
  else if (isHexadecimalDigit(cmd)) {
    char cmds[1];
    cmds[0] = cmd;
    int channel = (int) strtol(cmds, 0, 16);
    if (state == 'R') {
      if ((channel == 0) && cmd == '0') {
        displayBinaryRow(0);
      }
      if (channel > 0) {
        displayBinaryRow(channel);
      }
    }
    else if (state == 'L') {
      if ((channel == 0) && cmd == '0') {
        displayBinaryCol(0);
      }
      if (channel > 0) {
        displayBinaryCol(channel);
      }
    }
    else if (state == 'T') {
      if ((channel == 0) && cmd == '0') {
        displayBinaryRst(0);
      }
      if (channel > 0) {
        displayBinaryRst(channel);
      }
    }
    else {
      Serial.println("Invalid state -- please set state to row, column, or reset");
    }
  }
  else {
  }
}


void displayBinaryRow(byte numToShow)
{
  for (int i=0; i<4; i++)
  {
    if (bitRead(numToShow, i)==1)
    {
      digitalWrite(addrPinRow[i], HIGH);
    }
    else
    {
      digitalWrite(addrPinRow[i], LOW);
    }
  }
}

void displayBinaryCol(byte numToShow)
{
  for (int i=0; i<4; i++)
  {
    if (bitRead(numToShow, i)==1)
    {
      digitalWrite(addrPinCol[i], HIGH);
    }
    else
    {
      digitalWrite(addrPinCol[i], LOW);
    }
  }
}

void displayBinaryRst(byte numToShow)
{
  for (int i=0; i<4; i++)
  {
    if (bitRead(numToShow, i)==1)
    {
      digitalWrite(addrPinRst[i], HIGH);
    }
    else
    {
      digitalWrite(addrPinRst[i], LOW);
    }
  }
}