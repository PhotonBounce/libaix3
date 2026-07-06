<?php
header('Content-Type: text/plain');
$api_dir = '/home/photonb/public_html/opsbrief-api';
echo "API dir exists: " . (is_dir($api_dir) ? "YES" : "NO") . "\n";
if (is_dir($api_dir)) {
    echo "Files: " . implode(", ", array_diff(scandir($api_dir), ['.', '..'])) . "\n";
}

// Check .htaccess at root level
$root_htaccess = '/home/photonb/public_html/.htaccess';
echo "\nRoot .htaccess: " . (file_exists($root_htaccess) ? "EXISTS" : "NO") . "\n";
if (file_exists($root_htaccess)) {
    echo "Content:\n" . file_get_contents($root_htaccess) . "\n";
}

// Check opsbrief-api .htaccess
$api_htaccess = $api_dir . '/.htaccess';
echo "\nAPI .htaccess: " . (file_exists($api_htaccess) ? "EXISTS" : "NO") . "\n";
if (file_exists($api_htaccess)) {
    echo "Content:\n" . file_get_contents($api_htaccess) . "\n";
}
?>
