function level1() {
  if (condition1) {
    while (condition2) {
      for (let i = 0; i < 10; i++) {
        if (condition3) {
          function level2() {
            // Another nested function
            if (condition4) {
              try {
                function level3() {
                  // Deep nesting
                  while (true) {
                    if (true) {
                      {
                        // Anonymous block
                        console.log("Deep");
                      }
                    }
                  }
                }
              } catch (e) {
                console.log(e);
              }
            }
          }
        }
      }
    }
  }
  
  return "Done";
}