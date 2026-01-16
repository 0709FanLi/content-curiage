<template>
  <header class="topbar">
    <div class="topbar-left">
      <img class="topbar-logo" :src="logoIcon" alt="logo" />
      <span class="topbar-brand-text">合规内容专家</span>
    </div>

    <div class="topbar-right">
      <el-dropdown trigger="click" @command="handleCommand">
        <button class="topbar-user" type="button">
          <img class="topbar-user-icon" :src="userIcon" alt="user" />
          <span class="topbar-user-text">用户</span>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">
              <el-icon><SwitchButton /></el-icon>
              <span>退出登录</span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { SwitchButton } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores'

import logoIcon from '@/assets/icons/logo.png'
import userIcon from '@/assets/icons/user.png'

const router = useRouter()
const userStore = useUserStore()

const handleCommand = async (command: string) => {
  if (command !== 'logout') return

  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '确认退出', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await userStore.logout()
    router.push('/login')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('退出登录失败:', error)
    }
  }
}
</script>

<style scoped>
.topbar {
  height: 56px;
  background: linear-gradient(
    180deg,
    rgba(0, 184, 219, 0.2) 0%,
    rgba(0, 184, 219, 0.75) 100%
  );
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.topbar-logo {
  height: 32px;
  object-fit: contain;
}

.topbar-brand-text {
  color: #000;
  font-family: Tomorrow;
  font-size: 16px;
  font-style: normal;
  font-weight: 400;
  line-height: 16px; /* 100% */
  white-space: nowrap;
  margin-top: 12px;
}

.topbar-title {
  font-size: 20px;
  line-height: 16px;
  color: #000;
}

.topbar-right {
  display: flex;
  align-items: center;
}

.topbar-user {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  border-radius: 8px;
  padding: 0 10px;
  border: none;
  background: transparent;
  cursor: pointer;
}

.topbar-user:hover {
  background: rgba(255, 255, 255, 0.35);
}

.topbar-user-icon {
  width: 16px;
  height: 16px;
}

.topbar-user-text {
  font-size: 14px;
  font-weight: 500;
  color: #364153;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .topbar {
    padding: 0 16px;
  }
}
</style>

