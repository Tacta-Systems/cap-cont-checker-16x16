const int addrPinRow[] = {36,38,40,42}; // LSB first
const int addrPinCol[] = {37,39,41,43};
const int addrPinRst[] = {44,46,48,50};

const int autoAddrPinRow[] = {14, 2, 3, 4};
const int autoAddrPinCol[] = {5, 6, 7, 8};

const int COL_MUX_EN = 45;
const int RST_MUX_EN = 47;
const int ROW_MUX_EN = 49;
const int N_ROW_DEC_EN = 51;
const int N_ROW_MODE_SEL = 53;

const int AUTO_COL_MUX_EN = 9;
const int AUTO_ROW_MUX_EN = 11;
const int AUTO_N_ROW_DEC_EN = 12;
const int AUTO_N_ROW_MODE_SEL = 13;

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
  for (int i=0;i<4;i++)
  {
    pinMode(autoAddrPinRow[i], OUTPUT);
  }
  for (int i=0;i<4;i++)
  {
    pinMode(autoAddrPinCol[i], OUTPUT);
  }
  pinMode(COL_MUX_EN, OUTPUT);
  pinMode(RST_MUX_EN, OUTPUT);
  pinMode(ROW_MUX_EN, OUTPUT);
  pinMode(N_ROW_DEC_EN, OUTPUT);
  pinMode(N_ROW_MODE_SEL, OUTPUT);
  pinMode(AUTO_COL_MUX_EN, OUTPUT);
  pinMode(AUTO_ROW_MUX_EN, OUTPUT);
  pinMode(AUTO_N_ROW_DEC_EN, OUTPUT);
  pinMode(AUTO_N_ROW_MODE_SEL, OUTPUT);
  offMode();
  Serial.begin(115200);
}

void offMode() {
  digitalWrite(N_ROW_MODE_SEL, HIGH);
  digitalWrite(N_ROW_DEC_EN, HIGH);
  digitalWrite(AUTO_N_ROW_MODE_SEL, HIGH);
  digitalWrite(AUTO_N_ROW_DEC_EN, HIGH);
  digitalWrite(ROW_MUX_EN, LOW);
  digitalWrite(COL_MUX_EN, LOW);
  digitalWrite(RST_MUX_EN, LOW);
  digitalWrite(AUTO_ROW_MUX_EN, LOW);
  digitalWrite(AUTO_COL_MUX_EN, LOW);
}

char state = ' ';
/*
States:
the reason we're using these names is because we're limited to one character + can't use the letters 'A' - 'F'.
- 'O' for continuity check mode
- 'P' for capacitance check mode
- 'S' for reset sweep mode
- 'Z' for all off
- 'I' for binary counter disable mode
- 'R' for writing to the row muxes
- 'L' for writing to the column muxes
- 'T' for writing to the reset muxes
- 'U' for writing secondary board to "row/col" output
- 'V' for writing secondary board to "row/PZBIAS" output
- 'W' for writing secondary board to "col/PZBIAS" output
- 'X' for writing secondary board to "row/SHIELD" output
- 'Y' for writing secondary board to "col/SHIELD" output
*/
bool hasPrinted = false;

void loop() {
  char cmd;
  if (Serial.available() > 0) { // > 0
    cmd = Serial.read();
    hasPrinted = false;
  }
  if (cmd == 'O') { // continuity check mode
    state = 'O';
    digitalWrite(N_ROW_MODE_SEL, HIGH);
    digitalWrite(N_ROW_DEC_EN, HIGH);
    digitalWrite(ROW_MUX_EN, HIGH);
    digitalWrite(COL_MUX_EN, HIGH);
    digitalWrite(RST_MUX_EN, LOW);
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'P') { // capacitance checker mode
    state = 'P';
    digitalWrite(N_ROW_MODE_SEL, LOW);
    digitalWrite(N_ROW_DEC_EN, LOW);
    digitalWrite(ROW_MUX_EN, LOW);
    digitalWrite(COL_MUX_EN, HIGH);
    digitalWrite(RST_MUX_EN, LOW);
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'S') { // reset sweep mode
    state = 'S';
    digitalWrite(N_ROW_MODE_SEL, HIGH);
    digitalWrite(N_ROW_DEC_EN, HIGH);
    digitalWrite(ROW_MUX_EN, LOW);
    digitalWrite(COL_MUX_EN, LOW);
    digitalWrite(RST_MUX_EN, HIGH);
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'Z') { // off mode
    state = 'Z';
    offMode();
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'I') { // binary counter disable mode
    state = 'I';
    digitalWrite(N_ROW_MODE_SEL, LOW);
    digitalWrite(N_ROW_DEC_EN, HIGH);
    digitalWrite(ROW_MUX_EN, HIGH);
    digitalWrite(COL_MUX_EN, HIGH);
    digitalWrite(RST_MUX_EN, LOW);
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'R') { // write to row mode
    state = 'R';
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'L') { // write to column mode
    state = 'L';
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'T') { // write to reset mode
    state = 'T';
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'U') { // set secondary board to "row/col" mode
    state = 'U';
    digitalWrite(AUTO_ROW_MUX_EN, HIGH);
    digitalWrite(AUTO_COL_MUX_EN, HIGH);
    digitalWrite(AUTO_N_ROW_MODE_SEL, HIGH);
    digitalWrite(AUTO_N_ROW_DEC_EN, HIGH);
    setSecondaryRowMux(1);
    setSecondaryColMux(0);
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'V') { // set secondary board to "row/PZBIAS" mode
    state = 'V';
    digitalWrite(AUTO_ROW_MUX_EN, HIGH);
    digitalWrite(AUTO_COL_MUX_EN, HIGH);    
    digitalWrite(AUTO_N_ROW_MODE_SEL, HIGH);
    digitalWrite(AUTO_N_ROW_DEC_EN, HIGH);
    setSecondaryRowMux(1);
    setSecondaryColMux(1);
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'W') { // set secondary board to "col/PZBIAS" mode
    state = 'W';
    digitalWrite(AUTO_ROW_MUX_EN, HIGH);
    digitalWrite(AUTO_COL_MUX_EN, HIGH);    
    digitalWrite(AUTO_N_ROW_MODE_SEL, HIGH);
    digitalWrite(AUTO_N_ROW_DEC_EN, HIGH);
    setSecondaryRowMux(0);
    setSecondaryColMux(1);
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'X') { // set secondary board to "row/SHIELD" mode
    state = 'X';
    digitalWrite(AUTO_ROW_MUX_EN, HIGH);
    digitalWrite(AUTO_COL_MUX_EN, HIGH);    
    digitalWrite(AUTO_N_ROW_MODE_SEL, HIGH);
    digitalWrite(AUTO_N_ROW_DEC_EN, HIGH);
    setSecondaryRowMux(1);
    setSecondaryColMux(2);
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (cmd == 'Y') { // set secondary board to "col/SHIELD" mode
    state = 'Y';
    digitalWrite(AUTO_ROW_MUX_EN, HIGH);
    digitalWrite(AUTO_COL_MUX_EN, HIGH);    
    digitalWrite(AUTO_N_ROW_MODE_SEL, HIGH);
    digitalWrite(AUTO_N_ROW_DEC_EN, HIGH);
    setSecondaryRowMux(0);
    setSecondaryColMux(2);
    if (!hasPrinted) {
      hasPrinted = true;
    }
  }
  else if (isHexadecimalDigit(cmd)) { // characters 0-F drive indices 0-15 of whichever column's selected
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
      if (!hasPrinted) {
        hasPrinted = true;
      }
    }
    else if (state == 'L') {
      if ((channel == 0) && cmd == '0') {
        displayBinaryCol(0);
      }
      if (channel > 0) {
        displayBinaryCol(channel);
      }
      if (!hasPrinted) {
        hasPrinted = true;
      }
    }
    else if (state == 'T') {
      if ((channel == 0) && cmd == '0') {
        displayBinaryRst(0);
      }
      if (channel > 0) {
        displayBinaryRst(channel);
      }
      if (!hasPrinted) {
        hasPrinted = true;
      }
    }
    else {
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

void setSecondaryRowMux(byte numToShow)
{
  for (int i=0; i<4; i++) {
    if (bitRead(numToShow, i) == 1)
    {
      digitalWrite(autoAddrPinRow[i], HIGH);
    }
    else
    {
      digitalWrite(autoAddrPinRow[i], LOW);
    }
  }
}

void setSecondaryColMux(byte numToShow)
{
  for (int i=0; i<4; i++) {
    if (bitRead(numToShow, i) == 1)
    {
      digitalWrite(autoAddrPinCol[i], HIGH);
    }
    else
    {
      digitalWrite(autoAddrPinCol[i], LOW);
    }
  }
}