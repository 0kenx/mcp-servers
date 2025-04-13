import React from 'react';
import { useState, useEffect } from 'react';

// Constants
const MAX_ITEMS = 100;
const API_URL = 'https://api.example.com';

// Function
function fetchItems() {
    return fetch(API_URL);
}

// Export
export const ItemList = () => {
    const [items, setItems] = useState([]);
    return <div>{items.map(item => <div key={item.id}>{item.name}</div>)}</div>;
};

export default ItemList;