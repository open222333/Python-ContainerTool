import paramiko
import json
import os
import time


class ContainerTool:

    def __init__(self, host: str, ssh_user: str, ssh_port: int = 22, ssh_timeout: int = 10,
                 ssh_key_path: str = None, ssh_password: str = None, logger=None) -> None:
        """
        Args:
            host (str): 遠端主機 IP 或 hostname
            ssh_user (str): SSH 使用者
            ssh_port (int): SSH port，預設 22
            ssh_timeout (int): 連線逾時秒數，預設 10
            ssh_key_path (str, optional): SSH 私鑰路徑
            ssh_password (str, optional): SSH 密碼（優先使用金鑰）
            logger: Log instance
        """
        self.host = host
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port
        self.ssh_timeout = ssh_timeout
        self.ssh_key_path = ssh_key_path
        self.ssh_password = ssh_password
        self.logger = logger
        self._client = None

    def _connect(self):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            'hostname': self.host,
            'port': self.ssh_port,
            'username': self.ssh_user,
            'timeout': self.ssh_timeout,
        }

        if self.ssh_key_path:
            key_path = os.path.expanduser(self.ssh_key_path)
            connect_kwargs['pkey'] = paramiko.RSAKey.from_private_key_file(key_path)
        elif self.ssh_password:
            connect_kwargs['password'] = self.ssh_password
        else:
            # 使用預設 SSH agent / ~/.ssh/id_rsa
            connect_kwargs['look_for_keys'] = True

        client.connect(**connect_kwargs)
        return client

    def restart(self, container_name: str) -> tuple:
        """重啟遠端主機上的指定容器

        Args:
            container_name (str): Docker 容器名稱

        Returns:
            tuple: (success: bool, reason: str)
        """
        cmd = f'docker restart {container_name}'
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
            status_cmd = (
                f'docker inspect --format='
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
                log_cmd = f'docker logs --since {restart_ts} --tail 20 {container_name}'
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
        cmd = f'docker inspect --format="{{{{.State.Status}}}}" {container_name}'
        try:
            client = self._connect()
            stdin, stdout, stderr = client.exec_command(cmd)
            stdout.channel.recv_exit_status()
            out = stdout.read().decode().strip()
            client.close()
            return out if out else None
        except Exception as e:
            if self.logger:
                self.logger.error(f'[{self.host}] 查詢容器狀態失敗: {e}')
            print(f'[ERROR] {self.host} - 查詢容器狀態失敗: {e}')
            return None

    def list_containers(self) -> list:
        """列出遠端主機上的所有容器

        Returns:
            list: 容器資訊列表，失敗回傳 None
        """
        cmd = (
            'docker ps -a --format '
            '\'{"id":"{{.ID}}","name":"{{.Names}}","image":"{{.Image}}",'
            '"status":"{{.Status}}","state":"{{.State}}"}\''
        )
        try:
            client = self._connect()
            stdin, stdout, stderr = client.exec_command(cmd)
            stdout.channel.recv_exit_status()
            out = stdout.read().decode().strip()
            client.close()

            if not out:
                return []

            containers = []
            for line in out.splitlines():
                line = line.strip()
                if line:
                    try:
                        containers.append(json.loads(line))
                    except Exception:
                        pass
            return containers
        except Exception as e:
            if self.logger:
                self.logger.error(f'[{self.host}] 列出容器失敗: {e}')
            print(f'[ERROR] {self.host} - 列出容器失敗: {e}')
            return None

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
