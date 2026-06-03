<?php

declare(strict_types=1);

function e(?string $value): string
{
    return htmlspecialchars($value ?? '', ENT_QUOTES, 'UTF-8');
}

function redirect(string $path): never
{
    header('Location: ' . $path);
    exit;
}

function csrf_token(): string
{
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }

    return $_SESSION['csrf_token'];
}

function verify_csrf(): void
{
    $token = $_POST['csrf_token'] ?? '';
    if (!hash_equals($_SESSION['csrf_token'] ?? '', $token)) {
        http_response_code(419);
        exit('Session expiree. Rechargez la page puis reessayez.');
    }
}

function required(array $data, array $fields): array
{
    $errors = [];
    foreach ($fields as $field) {
        if (trim((string) ($data[$field] ?? '')) === '') {
            $errors[] = "Le champ {$field} est obligatoire.";
        }
    }

    return $errors;
}

function badge(string $status): string
{
    $labels = [
        'active' => 'Actif',
        'paused' => 'En pause',
        'done' => 'Termine',
        'todo' => 'A faire',
        'doing' => 'En cours',
    ];

    return $labels[$status] ?? $status;
}

function excerpt(?string $value, int $limit = 220): string
{
    $text = trim(preg_replace('/\s+/', ' ', $value ?? ''));
    if (strlen($text) <= $limit) {
        return $text;
    }

    return substr($text, 0, max(0, $limit - 3)) . '...';
}
