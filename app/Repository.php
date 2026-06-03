<?php

declare(strict_types=1);

final class Repository
{
    public function __construct(private readonly PDO $pdo)
    {
    }

    public function projects(): array
    {
        return $this->pdo->query(
            "SELECT p.*,
                (SELECT COUNT(*) FROM sources s WHERE s.project_id = p.id) AS source_count,
                (SELECT COUNT(*) FROM notes n WHERE n.project_id = p.id) AS note_count,
                (SELECT COUNT(*) FROM findings f WHERE f.project_id = p.id) AS finding_count,
                (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status != 'done') AS open_task_count
             FROM projects p
             ORDER BY p.updated_at DESC, p.created_at DESC"
        )->fetchAll();
    }

    public function project(int $id): ?array
    {
        $stmt = $this->pdo->prepare('SELECT * FROM projects WHERE id = ?');
        $stmt->execute([$id]);
        $project = $stmt->fetch();

        return $project ?: null;
    }

    public function createProject(array $data): int
    {
        $stmt = $this->pdo->prepare(
            'INSERT INTO projects (title, question, status, summary) VALUES (?, ?, ?, ?)'
        );
        $stmt->execute([
            trim($data['title']),
            trim($data['question']),
            $data['status'] ?: 'active',
            trim($data['summary'] ?? ''),
        ]);

        return (int) $this->pdo->lastInsertId();
    }

    public function updateProject(int $id, array $data): void
    {
        $stmt = $this->pdo->prepare(
            'UPDATE projects SET title = ?, question = ?, status = ?, summary = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
        );
        $stmt->execute([
            trim($data['title']),
            trim($data['question']),
            $data['status'] ?: 'active',
            trim($data['summary'] ?? ''),
            $id,
        ]);
    }

    public function deleteProject(int $id): void
    {
        $stmt = $this->pdo->prepare('DELETE FROM projects WHERE id = ?');
        $stmt->execute([$id]);
    }

    public function sources(int $projectId): array
    {
        $stmt = $this->pdo->prepare('SELECT * FROM sources WHERE project_id = ? ORDER BY created_at DESC');
        $stmt->execute([$projectId]);

        return $stmt->fetchAll();
    }

    public function addSource(int $projectId, array $data): void
    {
        $stmt = $this->pdo->prepare(
            'INSERT INTO sources (project_id, title, url, author, published_at, credibility, notes) VALUES (?, ?, ?, ?, ?, ?, ?)'
        );
        $stmt->execute([
            $projectId,
            trim($data['title']),
            trim($data['url'] ?? ''),
            trim($data['author'] ?? ''),
            trim($data['published_at'] ?? ''),
            max(1, min(5, (int) ($data['credibility'] ?? 3))),
            trim($data['notes'] ?? ''),
        ]);
        $this->touchProject($projectId);
    }

    public function notes(int $projectId): array
    {
        $stmt = $this->pdo->prepare('SELECT * FROM notes WHERE project_id = ? ORDER BY created_at DESC');
        $stmt->execute([$projectId]);

        return $stmt->fetchAll();
    }

    public function addNote(int $projectId, array $data): void
    {
        $stmt = $this->pdo->prepare(
            'INSERT INTO notes (project_id, title, body, tags) VALUES (?, ?, ?, ?)'
        );
        $stmt->execute([
            $projectId,
            trim($data['title']),
            trim($data['body']),
            trim($data['tags'] ?? ''),
        ]);
        $this->touchProject($projectId);
    }

    public function findings(int $projectId): array
    {
        $stmt = $this->pdo->prepare('SELECT * FROM findings WHERE project_id = ? ORDER BY confidence DESC, created_at DESC');
        $stmt->execute([$projectId]);

        return $stmt->fetchAll();
    }

    public function addFinding(int $projectId, array $data): void
    {
        $stmt = $this->pdo->prepare(
            'INSERT INTO findings (project_id, claim, evidence, confidence) VALUES (?, ?, ?, ?)'
        );
        $stmt->execute([
            $projectId,
            trim($data['claim']),
            trim($data['evidence'] ?? ''),
            max(1, min(5, (int) ($data['confidence'] ?? 3))),
        ]);
        $this->touchProject($projectId);
    }

    public function tasks(int $projectId): array
    {
        $stmt = $this->pdo->prepare(
            "SELECT * FROM tasks WHERE project_id = ? ORDER BY status = 'done', due_at = '', due_at ASC, created_at DESC"
        );
        $stmt->execute([$projectId]);

        return $stmt->fetchAll();
    }

    public function addTask(int $projectId, array $data): void
    {
        $stmt = $this->pdo->prepare(
            'INSERT INTO tasks (project_id, title, status, due_at) VALUES (?, ?, ?, ?)'
        );
        $stmt->execute([
            $projectId,
            trim($data['title']),
            $data['status'] ?: 'todo',
            trim($data['due_at'] ?? ''),
        ]);
        $this->touchProject($projectId);
    }

    public function updateTaskStatus(int $taskId, string $status): void
    {
        $stmt = $this->pdo->prepare('SELECT project_id FROM tasks WHERE id = ?');
        $stmt->execute([$taskId]);
        $task = $stmt->fetch();
        if (!$task) {
            return;
        }

        $update = $this->pdo->prepare('UPDATE tasks SET status = ? WHERE id = ?');
        $update->execute([$status, $taskId]);
        $this->touchProject((int) $task['project_id']);
    }

    public function deleteItem(string $table, int $id): void
    {
        $allowed = ['sources', 'notes', 'findings', 'tasks'];
        if (!in_array($table, $allowed, true)) {
            return;
        }

        $stmt = $this->pdo->prepare("SELECT project_id FROM {$table} WHERE id = ?");
        $stmt->execute([$id]);
        $row = $stmt->fetch();

        $delete = $this->pdo->prepare("DELETE FROM {$table} WHERE id = ?");
        $delete->execute([$id]);

        if ($row) {
            $this->touchProject((int) $row['project_id']);
        }
    }

    public function search(string $query): array
    {
        $like = '%' . $query . '%';
        $results = [];

        foreach ([
            'projects' => "SELECT id, title, question AS excerpt, 'project' AS kind, id AS project_id FROM projects WHERE title LIKE ? OR question LIKE ? OR summary LIKE ?",
            'sources' => "SELECT id, title, notes AS excerpt, 'source' AS kind, project_id FROM sources WHERE title LIKE ? OR url LIKE ? OR notes LIKE ?",
            'notes' => "SELECT id, title, body AS excerpt, 'note' AS kind, project_id FROM notes WHERE title LIKE ? OR body LIKE ? OR tags LIKE ?",
            'findings' => "SELECT id, claim AS title, evidence AS excerpt, 'finding' AS kind, project_id FROM findings WHERE claim LIKE ? OR evidence LIKE ? OR confidence LIKE ?",
        ] as $sql) {
            $stmt = $this->pdo->prepare($sql);
            $stmt->execute([$like, $like, $like]);
            $results = array_merge($results, $stmt->fetchAll());
        }

        return $results;
    }

    private function touchProject(int $projectId): void
    {
        $stmt = $this->pdo->prepare('UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?');
        $stmt->execute([$projectId]);
    }
}

