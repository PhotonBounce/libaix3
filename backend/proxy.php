<?php
// PHP proxy to Python FastAPI backend
header('Content-Type: application/json');

$method = $_SERVER['REQUEST_METHOD'];
$uri = $_SERVER['REQUEST_URI'];
$path = parse_url($uri, PHP_URL_PATH);
$path = preg_replace('#^/opsbrief-api/#', '/', $path);
if ($path === '' || $path === '/') $path = '/health';

// Collect headers
$headers = [];
foreach (getallheaders() as $k => $v) {
    $headers[] = "$k: $v";
}

// Collect body
$body = file_get_contents('php://input');

// Build curl command
$python = '/home/photonb/public_html/opsbrief-api/venv/bin/python3';
$app_dir = '/home/photonb/public_html/opsbrief-api';
$env = 'JWT_SECRET_KEY=opsbrief-local-dev-secret-key-32chars-min FREE_MODE=true';

// For now, return a mock response to test
$response = [
    'status' => 'ok',
    'message' => 'PHP proxy is working',
    'path' => $path,
    'method' => $method,
];
echo json_encode($response);
?>
