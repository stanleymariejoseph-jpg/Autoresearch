<?php

declare(strict_types=1);

session_start();

define('APP_ROOT', dirname(__DIR__));
define('DATA_DIR', APP_ROOT . DIRECTORY_SEPARATOR . 'data');

if (!is_dir(DATA_DIR)) {
    mkdir(DATA_DIR, 0777, true);
}

require_once APP_ROOT . '/app/helpers.php';
require_once APP_ROOT . '/app/Database.php';
require_once APP_ROOT . '/app/Repository.php';

$pdo = Database::connect(DATA_DIR . DIRECTORY_SEPARATOR . 'autoresearch.sqlite');
$repository = new Repository($pdo);

