# Описание
Кластер PostgreSQL состоит из 3-х Docker-контейнеров (postgres:9.6 + установка необходимого для Python): Master, Slave и Arbiter. Скрипт-агент написан на Python и запускается во всех контейнерах.

При потери сетевой связности Slave -> Master и подтверждении потери связи от Arbiter, Slave промоутится до мастера.

При этом если у Slave нет связи ни с Master, ни с Arbiter, промоут не происходит.

Промоут происходит путём создания триггер-файла "/tmp/promote_me".

Раз в секунду Slave проверяет связь Arbiter -> Master и Slave -> Master.

Раз в 5 секунд Master проверяет связь Master -> Slave и Master -> Arbiter. В случае отсутствия обеих связей происходит блокировка всех входящих подключений на Master через iptables, путём изменения политики по умолчанию на DROP.

# Запуск
Для запуска кластера: ```docker compose up```

Для запуска тестирования кластера запустить на хосте скрипт ```python writer.py```

# Тестирование кластера
Тест №1: умирает Slave (в середине теста Writer на хосте стопит контейнер ```docker compose stop pg-slave```).

При ```synchronous_commit = off```: потери отсутствуют.

При ```synchronous_commit = remote_apply```: потери отсутствуют.

Тест №2: умирает Master (в середине теста Writer на хосте стопит контейнер ```docker compose stop pg-master```).

При ```synchronous_commit = off```: потеряно 24 записи.

При ```synchronous_commit = remote_apply```: потери отсутствуют.
