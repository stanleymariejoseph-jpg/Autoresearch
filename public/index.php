<?php

declare(strict_types=1);

require_once dirname(__DIR__) . '/app/bootstrap.php';

$action = $_GET['action'] ?? 'dashboard';
$errors = [];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $postAction = $_POST['action'] ?? '';

    if ($postAction === 'create_project' || $postAction === 'update_project') {
        $errors = required($_POST, ['title', 'question']);
        if (!$errors) {
            if ($postAction === 'create_project') {
                $id = $repository->createProject($_POST);
            } else {
                $id = (int) $_POST['id'];
                $repository->updateProject($id, $_POST);
            }
            redirect('/?action=project&id=' . $id);
        }
        $action = $postAction === 'create_project' ? 'new_project' : 'edit_project';
    }

    if ($postAction === 'delete_project') {
        $repository->deleteProject((int) $_POST['id']);
        redirect('/');
    }

    if (in_array($postAction, ['add_source', 'add_note', 'add_finding', 'add_task'], true)) {
        $projectId = (int) $_POST['project_id'];
        $map = [
            'add_source' => ['title'],
            'add_note' => ['title', 'body'],
            'add_finding' => ['claim'],
            'add_task' => ['title'],
        ];
        $errors = required($_POST, $map[$postAction]);
        if (!$errors) {
            match ($postAction) {
                'add_source' => $repository->addSource($projectId, $_POST),
                'add_note' => $repository->addNote($projectId, $_POST),
                'add_finding' => $repository->addFinding($projectId, $_POST),
                'add_task' => $repository->addTask($projectId, $_POST),
            };
        }
        redirect('/?action=project&id=' . $projectId);
    }

    if ($postAction === 'task_status') {
        $repository->updateTaskStatus((int) $_POST['task_id'], $_POST['status'] ?? 'todo');
        redirect('/?action=project&id=' . (int) $_POST['project_id']);
    }

    if ($postAction === 'delete_item') {
        $repository->deleteItem($_POST['table'] ?? '', (int) $_POST['id']);
        redirect('/?action=project&id=' . (int) $_POST['project_id']);
    }
}

function layout(string $title, callable $content): void
{
    ?>
    <!doctype html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title><?= e($title) ?> - Autoresearch</title>
        <link rel="stylesheet" href="/assets/styles.css">
    </head>
    <body>
        <header class="topbar">
            <a class="brand" href="/">Autoresearch</a>
            <form class="search" method="get">
                <input type="hidden" name="action" value="search">
                <input name="q" value="<?= e($_GET['q'] ?? '') ?>" placeholder="Rechercher">
                <button>Rechercher</button>
            </form>
            <a class="button primary" href="/?action=new_project">Nouveau projet</a>
        </header>
        <main class="shell">
            <?php $content(); ?>
        </main>
    </body>
    </html>
    <?php
}

function projectForm(array $project = [], array $errors = []): void
{
    $isEdit = isset($project['id']);
    ?>
    <section class="panel narrow">
        <h1><?= $isEdit ? 'Modifier le projet' : 'Nouveau projet' ?></h1>
        <?php foreach ($errors as $error): ?>
            <p class="error"><?= e($error) ?></p>
        <?php endforeach; ?>
        <form method="post" class="stack">
            <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
            <input type="hidden" name="action" value="<?= $isEdit ? 'update_project' : 'create_project' ?>">
            <?php if ($isEdit): ?>
                <input type="hidden" name="id" value="<?= (int) $project['id'] ?>">
            <?php endif; ?>
            <label>Titre
                <input name="title" value="<?= e($project['title'] ?? '') ?>" required>
            </label>
            <label>Question de recherche
                <textarea name="question" rows="3" required><?= e($project['question'] ?? '') ?></textarea>
            </label>
            <label>Statut
                <select name="status">
                    <?php foreach (['active' => 'Actif', 'paused' => 'En pause', 'done' => 'Termine'] as $value => $label): ?>
                        <option value="<?= $value ?>" <?= ($project['status'] ?? 'active') === $value ? 'selected' : '' ?>><?= $label ?></option>
                    <?php endforeach; ?>
                </select>
            </label>
            <label>Resume
                <textarea name="summary" rows="5"><?= e($project['summary'] ?? '') ?></textarea>
            </label>
            <button class="primary"><?= $isEdit ? 'Enregistrer' : 'Creer le projet' ?></button>
        </form>
    </section>
    <?php
}

if ($action === 'new_project') {
    layout('Nouveau projet', fn() => projectForm([], $errors));
    exit;
}

if ($action === 'edit_project') {
    $project = $repository->project((int) ($_GET['id'] ?? $_POST['id'] ?? 0));
    if (!$project) {
        http_response_code(404);
        exit('Projet introuvable.');
    }
    layout('Modifier', fn() => projectForm($project, $errors));
    exit;
}

if ($action === 'export') {
    $project = $repository->project((int) ($_GET['id'] ?? 0));
    if (!$project) {
        http_response_code(404);
        exit('Projet introuvable.');
    }

    header('Content-Type: text/markdown; charset=utf-8');
    header('Content-Disposition: attachment; filename="autoresearch-' . (int) $project['id'] . '.md"');
    echo "# " . $project['title'] . "\n\n";
    echo "## Question\n\n" . $project['question'] . "\n\n";
    echo "## Resume\n\n" . ($project['summary'] ?: 'Aucun resume.') . "\n\n";
    echo "## Sources\n\n";
    foreach ($repository->sources((int) $project['id']) as $source) {
        echo "- {$source['title']}";
        echo $source['url'] ? " ({$source['url']})" : '';
        echo " - credibilite {$source['credibility']}/5\n";
    }
    echo "\n## Constats\n\n";
    foreach ($repository->findings((int) $project['id']) as $finding) {
        echo "- {$finding['claim']} (confiance {$finding['confidence']}/5)\n";
        if ($finding['evidence']) {
            echo "  Evidence: {$finding['evidence']}\n";
        }
    }
    echo "\n## Notes\n\n";
    foreach ($repository->notes((int) $project['id']) as $note) {
        echo "### {$note['title']}\n\n{$note['body']}\n\n";
    }
    exit;
}

if ($action === 'search') {
    $q = trim((string) ($_GET['q'] ?? ''));
    $results = $q === '' ? [] : $repository->search($q);
    layout('Recherche', function () use ($q, $results): void {
        ?>
        <section class="page-heading">
            <h1>Recherche</h1>
            <p><?= count($results) ?> resultat(s) pour "<?= e($q) ?>"</p>
        </section>
        <div class="grid">
            <?php foreach ($results as $result): ?>
                <article class="card">
                    <span class="meta"><?= e($result['kind']) ?></span>
                    <h2><a href="/?action=project&id=<?= (int) $result['project_id'] ?>"><?= e($result['title']) ?></a></h2>
                    <p><?= e(excerpt($result['excerpt'] ?? '')) ?></p>
                </article>
            <?php endforeach; ?>
        </div>
        <?php
    });
    exit;
}

if ($action === 'project') {
    $project = $repository->project((int) ($_GET['id'] ?? 0));
    if (!$project) {
        http_response_code(404);
        exit('Projet introuvable.');
    }
    $projectId = (int) $project['id'];
    $sources = $repository->sources($projectId);
    $notes = $repository->notes($projectId);
    $findings = $repository->findings($projectId);
    $tasks = $repository->tasks($projectId);

    layout($project['title'], function () use ($project, $projectId, $sources, $notes, $findings, $tasks): void {
        ?>
        <section class="project-header">
            <div>
                <span class="badge"><?= e(badge($project['status'])) ?></span>
                <h1><?= e($project['title']) ?></h1>
                <p><?= e($project['question']) ?></p>
            </div>
            <div class="actions">
                <a class="button" href="/?action=export&id=<?= $projectId ?>">Exporter</a>
                <a class="button" href="/?action=edit_project&id=<?= $projectId ?>">Modifier</a>
                <form method="post" onsubmit="return confirm('Supprimer ce projet ?')">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="delete_project">
                    <input type="hidden" name="id" value="<?= $projectId ?>">
                    <button class="danger">Supprimer</button>
                </form>
            </div>
        </section>

        <?php if ($project['summary']): ?>
            <section class="panel"><h2>Resume</h2><p><?= nl2br(e($project['summary'])) ?></p></section>
        <?php endif; ?>

        <section class="columns">
            <div class="panel">
                <h2>Sources</h2>
                <form method="post" class="stack compact">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="add_source">
                    <input type="hidden" name="project_id" value="<?= $projectId ?>">
                    <input name="title" placeholder="Titre de la source" required>
                    <input name="url" placeholder="URL">
                    <div class="row">
                        <input name="author" placeholder="Auteur">
                        <input name="published_at" placeholder="Date">
                        <input type="number" name="credibility" min="1" max="5" value="3" title="Credibilite">
                    </div>
                    <textarea name="notes" rows="3" placeholder="Notes sur la source"></textarea>
                    <button>Ajouter</button>
                </form>
                <?php foreach ($sources as $source): ?>
                    <article class="item">
                        <h3><?= e($source['title']) ?></h3>
                        <?php if ($source['url']): ?><a href="<?= e($source['url']) ?>" target="_blank" rel="noreferrer"><?= e($source['url']) ?></a><?php endif; ?>
                        <p><?= nl2br(e($source['notes'])) ?></p>
                        <small>Credibilite <?= (int) $source['credibility'] ?>/5</small>
                        <?php deleteButton('sources', (int) $source['id'], $projectId); ?>
                    </article>
                <?php endforeach; ?>
            </div>

            <div class="panel">
                <h2>Taches</h2>
                <form method="post" class="stack compact">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="add_task">
                    <input type="hidden" name="project_id" value="<?= $projectId ?>">
                    <input name="title" placeholder="Tache" required>
                    <div class="row">
                        <select name="status"><option value="todo">A faire</option><option value="doing">En cours</option><option value="done">Termine</option></select>
                        <input name="due_at" type="date">
                    </div>
                    <button>Ajouter</button>
                </form>
                <?php foreach ($tasks as $task): ?>
                    <article class="item task <?= e($task['status']) ?>">
                        <form method="post">
                            <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                            <input type="hidden" name="action" value="task_status">
                            <input type="hidden" name="project_id" value="<?= $projectId ?>">
                            <input type="hidden" name="task_id" value="<?= (int) $task['id'] ?>">
                            <select name="status" onchange="this.form.submit()">
                                <?php foreach (['todo', 'doing', 'done'] as $status): ?>
                                    <option value="<?= $status ?>" <?= $task['status'] === $status ? 'selected' : '' ?>><?= e(badge($status)) ?></option>
                                <?php endforeach; ?>
                            </select>
                        </form>
                        <strong><?= e($task['title']) ?></strong>
                        <small><?= e($task['due_at']) ?></small>
                        <?php deleteButton('tasks', (int) $task['id'], $projectId); ?>
                    </article>
                <?php endforeach; ?>
            </div>
        </section>

        <section class="columns">
            <div class="panel">
                <h2>Constats</h2>
                <form method="post" class="stack compact">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="add_finding">
                    <input type="hidden" name="project_id" value="<?= $projectId ?>">
                    <input name="claim" placeholder="Constat" required>
                    <textarea name="evidence" rows="3" placeholder="Preuves ou justification"></textarea>
                    <input type="number" name="confidence" min="1" max="5" value="3">
                    <button>Ajouter</button>
                </form>
                <?php foreach ($findings as $finding): ?>
                    <article class="item">
                        <h3><?= e($finding['claim']) ?></h3>
                        <p><?= nl2br(e($finding['evidence'])) ?></p>
                        <small>Confiance <?= (int) $finding['confidence'] ?>/5</small>
                        <?php deleteButton('findings', (int) $finding['id'], $projectId); ?>
                    </article>
                <?php endforeach; ?>
            </div>

            <div class="panel">
                <h2>Notes</h2>
                <form method="post" class="stack compact">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="add_note">
                    <input type="hidden" name="project_id" value="<?= $projectId ?>">
                    <input name="title" placeholder="Titre" required>
                    <textarea name="body" rows="5" placeholder="Note" required></textarea>
                    <input name="tags" placeholder="Tags">
                    <button>Ajouter</button>
                </form>
                <?php foreach ($notes as $note): ?>
                    <article class="item">
                        <h3><?= e($note['title']) ?></h3>
                        <p><?= nl2br(e($note['body'])) ?></p>
                        <small><?= e($note['tags']) ?></small>
                        <?php deleteButton('notes', (int) $note['id'], $projectId); ?>
                    </article>
                <?php endforeach; ?>
            </div>
        </section>
        <?php
    });
    exit;
}

function deleteButton(string $table, int $id, int $projectId): void
{
    ?>
    <form method="post" class="inline-delete">
        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
        <input type="hidden" name="action" value="delete_item">
        <input type="hidden" name="table" value="<?= e($table) ?>">
        <input type="hidden" name="id" value="<?= $id ?>">
        <input type="hidden" name="project_id" value="<?= $projectId ?>">
        <button title="Supprimer">Supprimer</button>
    </form>
    <?php
}

$projects = $repository->projects();
layout('Tableau de bord', function () use ($projects): void {
    ?>
    <section class="page-heading">
        <div>
            <h1>Tableau de bord</h1>
            <p><?= count($projects) ?> projet(s) de recherche</p>
        </div>
        <a class="button primary" href="/?action=new_project">Creer un projet</a>
    </section>
    <?php if (!$projects): ?>
        <section class="empty">
            <h2>Commencez votre premiere recherche</h2>
            <p>Ajoutez une question, collectez vos sources, puis transformez vos notes en constats exportables.</p>
            <a class="button primary" href="/?action=new_project">Nouveau projet</a>
        </section>
    <?php else: ?>
        <div class="grid">
            <?php foreach ($projects as $project): ?>
                <article class="card">
                    <span class="badge"><?= e(badge($project['status'])) ?></span>
                    <h2><a href="/?action=project&id=<?= (int) $project['id'] ?>"><?= e($project['title']) ?></a></h2>
                    <p><?= e($project['question']) ?></p>
                    <dl class="stats">
                        <div><dt>Sources</dt><dd><?= (int) $project['source_count'] ?></dd></div>
                        <div><dt>Notes</dt><dd><?= (int) $project['note_count'] ?></dd></div>
                        <div><dt>Constats</dt><dd><?= (int) $project['finding_count'] ?></dd></div>
                        <div><dt>Taches</dt><dd><?= (int) $project['open_task_count'] ?></dd></div>
                    </dl>
                </article>
            <?php endforeach; ?>
        </div>
    <?php endif; ?>
    <?php
});
