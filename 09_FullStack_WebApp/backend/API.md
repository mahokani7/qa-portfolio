# Todo API

This backend exposes a small to-do API under `/api/to-dos`.

## Base URL

`http://localhost:3001/api`

## Todo Object

```json
{
  "id": "6853f5d741f3e3d7ec2ce123",
  "title": "Buy milk",
  "completed": false,
  "createdAt": "2026-06-19T10:00:00.000Z",
  "updatedAt": "2026-06-19T10:00:00.000Z"
}
```

## Endpoints

### `GET /api/to-dos`

Returns all to-dos sorted by newest first.

Response: `200 OK`

```json
[
  {
    "id": "6853f5d741f3e3d7ec2ce123",
    "title": "Buy milk",
    "completed": false,
    "createdAt": "2026-06-19T10:00:00.000Z",
    "updatedAt": "2026-06-19T10:00:00.000Z"
  }
]
```

### `POST /api/to-dos`

Creates a new to-do.

Request body:

```json
{
  "title": "Buy milk"
}
```

Validation rules:

- `title` is required.
- `title` must be 100 characters or fewer.

Response: `201 Created`

```json
{
  "id": "6853f5d741f3e3d7ec2ce123",
  "title": "Buy milk",
  "completed": false,
  "createdAt": "2026-06-19T10:00:00.000Z",
  "updatedAt": "2026-06-19T10:00:00.000Z"
}
```

Validation error: `400 Bad Request`

```json
{
  "message": "A todo title is required."
}
```

### `POST /api/to-dos/:id/complete`

Toggles the `completed` state of a to-do and returns the updated object.

### `PUT /api/to-dos/:id`

Updates the `completed` state explicitly.

Request body:

```json
{
  "completed": true
}
```

Response: `200 OK`

```json
{
  "id": "6853f5d741f3e3d7ec2ce123",
  "title": "Buy milk",
  "completed": true,
  "createdAt": "2026-06-19T10:00:00.000Z",
  "updatedAt": "2026-06-19T10:10:00.000Z"
}
```

## Notes

- `/api/todos` is also available as a compatibility alias for some older routes.
- The API uses MongoDB through Mongoose.