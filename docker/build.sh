mkdir -p itassets
cp -rv ../itassets/* itassets/

docker build -t itassets .

