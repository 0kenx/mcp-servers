const { 
    user: { 
        name, 
        address: { 
            city, 
            coordinates: [lat, lng] 
        } 
    }, 
    settings: { theme = 'default' } = {} 
} = response;

function processData({ items = [], config: { sort = true, filter = false } = {} }) {
    return items.filter(x => x > 10);
}