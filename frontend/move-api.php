<?php
// Deploy API to separate path
header('Content-Type: text/plain');
set_time_limit(300);

$src = '/home/photonb/public_html/opsbrief/api';
$dst = '/home/photonb/public_html/opsbrief-api';

echo "=== Moving API to separate path ===\n";

// Create destination
if (!is_dir($dst)) {
    mkdir($dst, 0755, true);
}

// Copy files
shell_exec("cp -r $src/* $dst/ 2>&1");
echo "Copied backend files to $dst\n";

// Create .htaccess for Passenger
$htaccess = "PassengerPython /home/photonb/public_html/opsbrief-api/venv/bin/python3\n";
$htaccess .= "PassengerAppRoot /home/photonb/public_html/opsbrief-api\n";
$htaccess .= "PassengerStartupFile passenger_wsgi.py\n";
$htaccess .= "PassengerEnabled on\n";
file_put_contents("$dst/.htaccess", $htaccess);
echo "Created .htaccess\n";

echo "\nDone. API should be at https://photon-bounce.com/opsbrief-api/\n";
?>
