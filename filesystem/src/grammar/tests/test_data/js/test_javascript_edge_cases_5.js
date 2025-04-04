function* numberGenerator() {
    let i = 0;
    while (true) {
        yield i++;
    }
}

class SequenceGenerator {
    *generate(start, end) {
        for (let i = start; i <= end; i++) {
            yield i;
        }
    }
    
    async *asyncGenerate(start, end) {
        for (let i = start; i <= end; i++) {
            await sleep(100);
            yield i;
        }
    }
}