// Async function declaration
async function fetchData() {
    const response = await fetch('/api/data');
    return response.json();
}

// Async arrow function
const getData = async () => {
    const data = await fetchData();
    return data.filter(item => item.active);
};