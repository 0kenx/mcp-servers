function calculate(x) {
  return x * x;
}

class Point {
  constructor(x, y) {
    this.x = x;
    this.y = y;
  }

  display() {
    console.log(`Point(${this.x}, ${this.y})`);
  }
}