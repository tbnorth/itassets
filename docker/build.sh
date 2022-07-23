mkdir -p itassets
cp -rv ../itassets/* itassets/
cp -v ../requirements.txt itassets/

docker build -t itassets .

