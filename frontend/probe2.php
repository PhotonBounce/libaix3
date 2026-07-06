<?php
header('Content-Type: text/plain');
// Check for cPanel alternate Python installations
$paths = [
    '/opt/alt/python',
    '/opt/alt/python311',
    '/opt/alt/python310',
    '/usr/local/bin/python3',
    '/usr/bin/python3',
    '/opt/python',
];
foreach ($paths as $p) {
    echo "$p: " . (is_dir($p) || is_file($p) ? "EXISTS" : "NOT FOUND") . "\n";
}
// Check for cPanel features
echo "\nChecking cPanel features...\n";
echo "Home: " . getenv('HOME') . "\n";
echo "Document Root: " . getenv('DOCUMENT_ROOT') . "\n";
?>
