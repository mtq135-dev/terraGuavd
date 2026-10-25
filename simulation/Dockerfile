FROM px4io/px4-sitl-gazebo@sha256:29a5a1b5af77e5d39b67bc6664d36acead63f9dfb829475216522b1feec8036e
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-venv && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/terraguavd
COPY requirements-lock.txt /tmp/requirements-lock.txt
RUN /opt/terraguavd/bin/pip install --no-cache-dir -r /tmp/requirements-lock.txt
COPY terraguavd_simulation /srv/terraguavd_simulation
WORKDIR /srv
ENV HEADLESS=1 PX4_SIM_MODEL=gz_x500
ENTRYPOINT ["/opt/terraguavd/bin/python", "-m", "uvicorn", "terraguavd_simulation.server:app", "--host", "0.0.0.0", "--port", "8090"]
