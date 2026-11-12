# 指令的實作在 tools/ (Python 標準函式庫, 可以不經 make 執行: python3 -m tools <指令>)。
# 新增指令 = 在 tools/commands/ 加一個模組並登記到 tools/__main__.py, 再把名稱加進 TARGETS。

TARGETS = init start stop status logs db jobs backup check e2e gen-types release doctor

.DEFAULT_GOAL := help
.PHONY: help $(TARGETS)

# 第一個字是已知指令時, 後面的字都是它的參數 (`make db migration "add phone"`),
# 接住它們不當成目標; 打錯的指令名稱仍然報錯。
ifneq ($(filter $(firstword $(MAKECMDGOALS)),$(TARGETS)),)
  CMD_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  PLAIN_ARGS := $(filter-out $(TARGETS) help,$(CMD_ARGS))
  ifneq ($(PLAIN_ARGS),)
    .PHONY: $(PLAIN_ARGS)
    $(eval $(PLAIN_ARGS):;@:)
  endif
%:
	@:
endif

# `make db help` 的 help 是 db 的參數: 只有它是第一個字 (或什麼都沒給) 時才印總覽。
help:
	@$(if $(filter-out help,$(firstword $(MAKECMDGOALS))),:,python3 -m tools help)

$(TARGETS):
	@$(if $(filter $@,$(firstword $(MAKECMDGOALS))),python3 -m tools $@ $(CMD_ARGS),:)
