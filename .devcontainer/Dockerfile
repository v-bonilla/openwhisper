# Using https://github.com/anthropics/claude-code/blob/main/.devcontainer/Dockerfile as base
FROM python:3.11-slim-bookworm

#################### OS SETUP ####################
# # Create volume mount points for Claude settings
# VOLUME ["/home/user/.claude", "/home/user/.claude.json"]

ARG TZ
ENV TZ="$TZ"

# Install common development dependencies
RUN apt-get update && apt-get install -y \
    less \
    git \
    procps \
    sudo \
    fzf \
    zsh \
    man-db \
    unzip \
    gnupg2 \
    gh \
    iptables \
    ipset \
    iproute2 \
    dnsutils \
    aggregate \
    jq \
    curl \
    wget \
    tmux \
    sudo \
    nano \
    net-tools \
    htop \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

RUN ARCH=$(dpkg --print-architecture) && \
    wget "https://github.com/dandavison/delta/releases/download/0.18.2/git-delta_0.18.2_${ARCH}.deb" && \
    sudo dpkg -i "git-delta_0.18.2_${ARCH}.deb" && \
    rm "git-delta_0.18.2_${ARCH}.deb"

#################### OS SETUP ####################

#################### USER SETUP ####################
# Create user with sudo access
RUN groupadd --gid 1010 user \
    && useradd --uid 1010 --gid 1010 -m user \
    && echo user ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/user \
    && chmod 0440 /etc/sudoers.d/user

# Ensure default user has access to /usr/local/share to install claude code
RUN mkdir -p /usr/local/share/npm-global && \
    chown -R user:user /usr/local/share

# Persist bash history.
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    && mkdir /commandhistory \
    && touch /commandhistory/.bash_history \
    && chown -R user:user /commandhistory
#################### USER SETUP ####################

#################### PROJECT SETUP ####################
# Set `DEVCONTAINER` environment variable to help with orientation
ENV DEVCONTAINER=true

# Create workspace and config directories and set permissions
RUN mkdir -p /workspace && \
    chown -R user:user /workspace

# Set working directory (required)
ARG WORKDIR
WORKDIR ${WORKDIR}
#################### PROJECT SETUP ####################

#################### UV SETUP ####################
# Install uv (Python package manager) for the user
USER user
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH for the user
ENV PATH="/home/user/.local/bin:$PATH"
#################### UV SETUP ####################

#################### TERMINAL SETUP ####################
# Set up non-root user
USER user

# Install global packages
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin

# Set the default shell to zsh rather than sh
ENV SHELL=/bin/zsh

# Default powerline10k theme
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v1.2.1/zsh-in-docker.sh)" -- \
    -p git \
    -p fzf \
    -a "export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    -x

RUN echo "alias ll=\"ls -la\"" >> /home/user/.zshrc
#################### TERMINAL SETUP ####################

#################### CLAUDE CODE SETUP ####################
# Create workspace and config directories and set permissions
RUN mkdir -p /home/user/.claude && \
    chown -R user:user /home/user/.claude

# Install Claude
RUN npm install -g @anthropic-ai/claude-code
#################### CLAUDE CODE SETUP ####################

#################### CODEX SETUP ####################
RUN npm install -g @openai/codex    
#################### CODEX SETUP ####################

USER user

# Default command
CMD ["zsh"]
