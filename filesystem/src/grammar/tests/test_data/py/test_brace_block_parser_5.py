void outer() {
    int x = 10;
    if (x > 5) {
        printf("Greater");
        function inner() { // JS style nested function
           return x;
        }
    } // end if
} // end outer