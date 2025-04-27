
#!/bin/bash
echo "Script starting"
counter=0
while [ $counter -lt 10 ]; do
    echo "Counter: $counter"
    counter=$((counter + 1))
    sleep 1
done
echo "Script complete"
