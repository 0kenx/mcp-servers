function calculateTotal(items, tax
    return items.reduce((sum, item) => sum + item.price, 0) * (1 + tax);

class ShoppingCart {
    constructor(

    addItem(item {
        this.items.push(item);

    getTotal(
        return this.items.reduce((sum, item) => sum + item.price, 0);
}