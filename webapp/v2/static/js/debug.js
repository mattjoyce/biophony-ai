// Simple debug script to test if JavaScript is working
console.log('Debug script loaded successfully');

// Test API call
async function testAPI() {
    try {
        console.log('Testing API call to /api/dates...');
        const response = await fetch('/api/dates');
        const result = await response.json();
        console.log('API Response:', result);
        
        if (result.success && result.data.length > 0) {
            console.log(`✓ API working! Found ${result.data.length} dates`);
            document.body.innerHTML += `<div style="color: green; position: fixed; top: 10px; right: 10px; background: white; padding: 10px; border: 1px solid green;">✓ API Working: ${result.data.length} dates found</div>`;
        } else {
            console.error('API returned no data');
            document.body.innerHTML += `<div style="color: red; position: fixed; top: 10px; right: 10px; background: white; padding: 10px; border: 1px solid red;">✗ API Error: No data</div>`;
        }
    } catch (error) {
        console.error('API call failed:', error);
        document.body.innerHTML += `<div style="color: red; position: fixed; top: 10px; right: 10px; background: white; padding: 10px; border: 1px solid red;">✗ API Failed: ${error.message}</div>`;
    }
}

// Test when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, testing API...');
    testAPI();
});