# TEN — IELTS Writing Тексеру Жүйесі

Streamlit + Supabase негізіндегі IELTS Writing Task 1 / Task 2 автоматты тексеру жүйесі.

## Беттер

| Файл | Сипаттама |
|------|-----------|
| `app.py` | IELTS Writing Task 1 — оқушы беті |
| `app2.py` | IELTS Writing Task 2 — оқушы беті |
| `teacher.py` | Мұғалім панелі (Live, Античит, Нәтижелер, Журнал) |
| `utils.py` | Ортақ функциялар |

## Іске қосу

### 1. Supabase кестелерін жасау

Supabase → SQL Editor-ға төмендегіні қосыңыз:

```sql
-- Оқушылар тізімі
create table if not exists students (
  id   bigint generated always as identity primary key,
  name text not null unique
);

-- RLS
alter table students enable row level security;
create policy "Барлығы оқи алады" on students for select using (true);
create policy "Тек service_role жаза алады" on students for all
  using (auth.role() = 'service_role');
```

### 2. Оқушыларды қосу

```sql
insert into students (name) values
  ('Аяулым'), ('Тасним'), ('Каусар'), ('Асия'),
  ('Қарақат 10'), ('Алихан'), ('Бексұлтан'), ('Ақайдар'),
  ('Ихсан'), ('Иман'), ('Амиржан'), ('Алихан 9'),
  ('Ақбота'), ('Қарақат 9'), ('Аяна'), ('Жанна'),
  ('Алиасқар'), ('Молдияр'), ('Альмир'), ('Алижан'),
  ('Баянсұлу'), ('Дана'), ('Айғаным'), ('Ақнұр')
on conflict (name) do nothing;
```

### 3. Secrets қосу

`secrets.toml.example` файлын үлгі ретінде пайдаланып, Streamlit Cloud-та **Settings → Secrets** бөліміне мәндерді қойыңыз:

```toml
[supabase]
url         = "https://СІЗДІҢ_PROJECT.supabase.co"
key         = "СІЗДІҢ_ANON_KEY"
service_key = "СІЗДІҢ_SERVICE_ROLE_KEY"
```

### 4. Streamlit Cloud-та Deploy

1. GitHub-қа push жасаңыз
2. [share.streamlit.io](https://share.streamlit.io) → New app
3. Repo, branch, main file (`app.py`) таңдаңыз
4. Secrets қойыңыз → Deploy!

## Қажетті пакеттер

```
streamlit
supabase
Pillow
pandas
requests
```
