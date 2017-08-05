for test in test_*.py
do
    coverage run -p "$test"
done

coverage combine
coverage html --omit=/usr/*
