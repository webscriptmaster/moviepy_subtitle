FROM ubuntu

RUN apt update
RUN apt install wget build-essential libssl*  -y
RUN apt-get install libffi-dev nano -y

RUN wget https://www.python.org/ftp/python/3.10.14/Python-3.10.14.tgz
RUN tar -xzvf Python-3.10.14.tgz
RUN cd Python-3.10.14
WORKDIR Python-3.10.14
RUN ./configure --enable-optimizations --with-system-ffi
RUN make -j 16
RUN apt install libespeak-dev zlib1g-dev libmupdf-dev libfreetype6-dev ffmpeg espeak imagemagick git -y
RUN make altinstall

RUN python3.10 -m pip install numpy
RUN python3.10 -m pip install aeneas
RUN python3.10 -m pip install moviepy
RUN python3.10 -m pip install pathlib
RUN python3.10 -m pip install pysrt
RUN python3.10 -m pip install flask 
RUN python3.10 -m pip install Pillow==9.5.0 

COPY ./policy.xml /etc/ImageMagick-6/policy.xml

RUN mkdir /app
RUN mkdir /app/static/
RUN mkdir /app/static/output_root/
RUN mkdir /app/static/output_root/final
WORKDIR /app

COPY ./test.py /app
COPY ./web.py /app

CMD python3.10 web.py
