import paramiko
import json
import os
import time


def _load_private_key(path: str):
    """自動偵測金鑰類型並載入（RSA / Ed25519 / ECDSA / DSS）。"""
    expanded = os.path.expanduser(path)
    for key_cls in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.DSSKey):
        try:
            return key_cls.from_private_key_file(expanded)
        except paramiko.SSHException:
            continue
    raise paramiko.SSHException(f'無法載入私鑰：{path}（不支援的格式或金鑰損毀）')


def _make_ssh_client(host, ssh_user, ssh_port, ssh_timeout, ssh_key_path, ssh_password):
    """建立並回傳已連線的 paramiko SSHClient。"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs = {
        'hostname': host,
        'port': ssh_port,
        'username': ssh_user,
        'timeout': ssh_timeout,
        'look_for_keys': False,
        'allow_agent': False,
    }
    if ssh_key_path:
        kwargs['pkey'] = _load_private_key(ssh_key_path)
    elif ssh_password:
        kwargs['password'] = ssh_password
    else:
        kwargs['look_for_keys'] = True
    client.connect(**kwargs)
    return client


def _parse_docker_ps(output: str) -> list:
    """解析 docker ps 純文字表格輸出，回傳 container dict 列表。"""
    lines = output.strip().splitlines()
    if len(lines) < 2:
        return []

    header = lines[0]
    col_names = ['CONTAINER ID', 'IMAGE', 'COMMAND', 'CREATED', 'STATUS', 'PORTS', 'NAMES']
    starts = [header.find(col) for col in col_names if header.find(col) >= 0]

    containers = []
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = [
            line[starts[i]: starts[i + 1] if i + 1 < len(starts) else len(line)].strip()
            for i in range(len(starts))
        ]
        containers.append({
            'id': fields[0] if len(fields) > 0 else '',
            'name': fields[6] if len(fields) > 6 else '',
            'image': fields[1] if len(fields) > 1 else '',
            'status': fields[4] if len(fields) > 4 else '',
            'state': 'running',  # docker ps 無 -a，只顯示執行中
        })
    return containers


class ContainerTool:

    def __init__(self, host: str, ssh_user: str, ssh_port: int = 22, ssh_timeout: int = 10,
                 ssh_key_path: str = None, ssh_password: str = None, use_sudo: bool = False,
                 logger=None) -> None:
        """
        Args:
            host (str): 遠端主機 IP 或 hostname
            ssh_user (str): SSH 使用者
            ssh_port (int): SSH port，預設 22
            ssh_timeout (int): 連線逾時秒數，預設 10
            ssh_key_path (str, optional): SSH 私鑰路徑
            ssh_password (str, optional): SSH 密碼（優先使用金鑰）
            use_sudo (bool): 非 root 帳號時設為 True，docker 指令自動加 sudo
            logger: Log instance
        """
        self.host = host
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port
        self.ssh_timeout = ssh_timeout
        self.ssh_key_path = ssh_key_path
        self.ssh_password = ssh_password
        self.use_sudo = use_sudo
        self.logger = logger
        self._client = None

    def _docker(self, subcmd: str) -> str:
        prefix = 'sudo docker' if self.use_sudo else 'docker'
        return f'{prefix} {subcmd}'

    def _connect(self):
        return _make_ssh_client(
            self.host, self.ssh_user, self.ssh_port,
            self.ssh_timeout, self.ssh_key_path, self.ssh_password,
        )

    def restart(self, container_name: str) -> tuple:
        """重啟遠端主機上的指定容器

        Args:
            container_name (str): Docker 容器名稱

        Returns:
            tuple: (success: bool, reason: str)
        """
        cmd = self._docker(f'restart {container_name}')
        if self.logger:
            self.logger.info(f'[{self.host}] 執行: {cmd}')

        try:
            client = self._connect()

            # 記錄重啟前時間（Unix timestamp，用於過濾 log）
            _, ts_out, _ = client.exec_command('date +%s')
            ts_out.channel.recv_exit_status()
            restart_ts = ts_out.read().decode().strip() or '0'

            # 執行重啟
            _, stdout, stderr = client.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()
            err = stderr.read().decode().strip()

            if exit_code != 0:
                client.close()
                reason = err or f'exit code {exit_code}'
                if self.logger:
                    self.logger.error(f'[{self.host}] 容器 {container_name} 重啟失敗: {reason}')
                print(f'[FAIL] {self.host} - 容器 {container_name} 重啟失敗: {reason}')
                return False, reason

            # 等待數秒讓容器有機會 crash
            time.sleep(5)

            # 確認容器狀態（running / restarting / exited ...）
            status_cmd = self._docker(
                f'inspect --format='
                f'"{{{{.State.Status}}}} {{{{.State.ExitCode}}}} {{{{.State.Error}}}}"'
                f' {container_name}'
            )
            _, stdout, _ = client.exec_command(status_cmd)
            stdout.channel.recv_exit_status()
            inspect_out = stdout.read().decode().strip()
            parts = inspect_out.split(' ', 2)
            state = parts[0] if parts else ''
            exit_code_c = parts[1] if len(parts) > 1 else ''
            container_err = parts[2] if len(parts) > 2 else ''

            if state != 'running':
                # 取出重啟後的 log 作為失敗原因
                log_cmd = self._docker(f'logs --since {restart_ts} --tail 20 {container_name}')
                _, log_stdout, log_stderr = client.exec_command(log_cmd)
                log_stdout.channel.recv_exit_status()
                log_out = log_stdout.read().decode().strip()
                log_err = log_stderr.read().decode().strip()
                client.close()

                log_content = log_err or log_out or container_err or ''
                reason = f'容器狀態為 {state}（exit code {exit_code_c}）'
                if log_content:
                    reason += f': {log_content}'
                if self.logger:
                    self.logger.error(f'[{self.host}] 容器 {container_name} {reason}')
                print(f'[FAIL] {self.host} - 容器 {container_name} {reason}')
                return False, reason

            client.close()
            if self.logger:
                self.logger.info(f'[{self.host}] 容器 {container_name} 重啟成功')
            print(f'[OK] {self.host} - 容器 {container_name} 重啟成功')
            return True, ''

        except Exception as e:
            reason = str(e)
            if self.logger:
                self.logger.error(f'[{self.host}] SSH 連線失敗: {reason}')
            print(f'[ERROR] {self.host} - SSH 連線失敗: {reason}')
            return False, reason

    def status(self, container_name: str) -> str:
        """查詢遠端主機上的容器狀態

        Args:
            container_name (str): Docker 容器名稱

        Returns:
            str: 容器狀態字串，失敗回傳 None
        """
        cmd = self._docker(f'inspect --format="{{{{.State.Status}}}}" {container_name}')
        try:
            client = self._connect()
            _, stdout, _ = client.exec_command(cmd)
            stdout.channel.recv_exit_status()
            out = stdout.read().decode().strip()
            client.close()
            return out if out else None
        except Exception as e:
            if self.logger:
                self.logger.error(f'[{self.host}] 查詢容器狀態失敗: {e}')
            print(f'[ERROR] {self.host} - 查詢容器狀態失敗: {e}')
            return None

    def list_containers(self) -> tuple:
        """列出遠端主機上的所有容器

        Returns:
            tuple: (containers: list | None, error: str)
        """
        cmd = self._docker(
            'ps -a --format '
            '\'{"id":"{{.ID}}","name":"{{.Names}}","image":"{{.Image}}",'
            '"status":"{{.Status}}","state":"{{.State}}"}\''
        )
        try:
            client = self._connect()
            _, stdout, stderr = client.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            client.close()

            if err:
                print(f'[WARN] {self.host} - list_containers stderr: {err}')
            if exit_code != 0 or not out:
                return None, err or f'exit code {exit_code}'

            containers = []
            for line in out.splitlines():
                line = line.strip()
                if line:
                    try:
                        containers.append(json.loads(line))
                    except Exception:
                        pass
            return containers, ''
        except Exception as e:
            if self.logger:
                self.logger.error(f'[{self.host}] 列出容器失敗: {e}')
            print(f'[ERROR] {self.host} - 列出容器失敗: {e}')
            return None, str(e)

    def reboot_host(self) -> tuple:
        """重開遠端主機

        Returns:
            tuple: (success: bool, reason: str)
        """
        if self.logger:
            self.logger.info(f'[{self.host}] 執行主機重開機')
        try:
            client = self._connect()
            client.exec_command('sudo reboot')
            client.close()
            if self.logger:
                self.logger.info(f'[{self.host}] 主機重開機指令已送出')
            print(f'[OK] {self.host} - 主機重開機指令已送出')
            return True, ''
        except Exception as e:
            reason = str(e)
            if self.logger:
                self.logger.error(f'[{self.host}] 主機重開機失敗: {reason}')
            print(f'[ERROR] {self.host} - 主機重開機失敗: {reason}')
            return False, reason


class RestrictedContainerTool:
    """透過 authorized_keys command= 白名單 SSH 帳號進行 Docker 操作。

    每次操作開啟一個 SSH exec channel 送出單一指令（即 $SSH_ORIGINAL_COMMAND），
    由遠端的白名單腳本（如 allowed_commands.sh）決定是否允許執行。

    限制：
    - list_containers 使用 ``docker ps``（無 -a），只顯示執行中的容器。
    - restart 不做重啟後的狀態確認（無法多次送指令）。
    - reboot_host 需白名單含 reboot 指令才有效。
    """

    def __init__(self, host: str, ssh_user: str, ssh_port: int = 22,
                 ssh_timeout: int = 10, ssh_key_path: str = None,
                 ssh_password: str = None, logger=None) -> None:
        self.host = host
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port
        self.ssh_timeout = ssh_timeout
        self.ssh_key_path = ssh_key_path
        self.ssh_password = ssh_password
        self.logger = logger

    def _exec(self, command: str) -> tuple:
        """建立新連線，送出單一指令，回傳 (exit_code, stdout, stderr)。"""
        client = _make_ssh_client(
            self.host, self.ssh_user, self.ssh_port,
            self.ssh_timeout, self.ssh_key_path, self.ssh_password,
        )
        _, stdout, stderr = client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode(errors='replace').strip()
        err = stderr.read().decode(errors='replace').strip()
        client.close()
        return exit_code, out, err

    def list_containers(self) -> tuple:
        """列出執行中的容器（docker ps）。

        Returns:
            tuple: (containers: list | None, error: str)
        """
        try:
            exit_code, out, err = self._exec('docker ps')
            if exit_code != 0 or not out:
                return None, err or f'exit code {exit_code}'
            return _parse_docker_ps(out), ''
        except Exception as e:
            if self.logger:
                self.logger.error(f'[{self.host}] 列出容器失敗: {e}')
            return None, str(e)

    def restart(self, container_name: str) -> tuple:
        """重啟指定容器（docker restart <name>），不做事後狀態確認。

        Returns:
            tuple: (success: bool, reason: str)
        """
        cmd = f'docker restart {container_name}'
        if self.logger:
            self.logger.info(f'[{self.host}] 執行: {cmd}')
        try:
            exit_code, _, err = self._exec(cmd)
            if exit_code != 0:
                reason = err or f'exit code {exit_code}'
                if self.logger:
                    self.logger.error(f'[{self.host}] 容器 {container_name} 重啟失敗: {reason}')
                return False, reason
            if self.logger:
                self.logger.info(f'[{self.host}] 容器 {container_name} 重啟成功')
            return True, ''
        except Exception as e:
            if self.logger:
                self.logger.error(f'[{self.host}] SSH 連線失敗: {e}')
            return False, str(e)

    def reboot_host(self) -> tuple:
        """重開主機（需白名單含 reboot 指令）。

        Returns:
            tuple: (success: bool, reason: str)
        """
        if self.logger:
            self.logger.info(f'[{self.host}] 執行主機重開機')
        try:
            client = _make_ssh_client(
                self.host, self.ssh_user, self.ssh_port,
                self.ssh_timeout, self.ssh_key_path, self.ssh_password,
            )
            client.exec_command('reboot')
            client.close()
            if self.logger:
                self.logger.info(f'[{self.host}] 主機重開機指令已送出')
            return True, ''
        except Exception as e:
            reason = str(e)
            if self.logger:
                self.logger.error(f'[{self.host}] 主機重開機失敗: {reason}')
            return False, reason
