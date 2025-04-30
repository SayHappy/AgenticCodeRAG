const __templateJs = require("./templates.js");
const __mergePageOptions = require("../../util/mergePageOptions.js");
Page(__mergePageOptions({
  data: {
    alertText: '警示文案',
    itemColor: '#ff0000',
    itemListLength: 4,
    apiData: {
      content: '',
      success: false,
      fail: false,
      complete: false
    }
  },
  handleAlertText(e) {
    this.setData({
      alertText: e.detail.value
    });
  },
  handleItemColor(e) {
    this.setData({
      itemColor: e.detail.value
    });
  },
  handleItemListLength(e) {
    this.setData({
      itemListLength: e.detail.value
    });
  },
  resetApiData() {
    this.setData({
      apiData: {
        success: false,
        fail: false,
        complete: false,
        content: ''
      }
    });
  },
  updateApiData(type, content) {
    const apiData = {
      ...this.data.apiData
    };
    apiData[type] = true;
    apiData.content = content;
    this.setData({
      apiData
    });
  },
  onShareAppMessage() {
    return {
      title: '操作菜单',
      path: 'packageAPI/pages/action-sheet/action-sheet'
    };
  },
  itemList() {
    return Array(this.data.itemListLength - 0).fill('item');
  },
  common(options) {
    this.resetApiData();
    xhs.showActionSheet({
      ...options,
      success: res => {
        this.updateApiData('success', res);
      },
      fail: res => {
        this.updateApiData('fail', res);
      },
      complete: res => {
        this.updateApiData('complete', res);
      }
    });
  },
  actionSheetTap() {
    this.common({
      itemList: this.itemList()
    });
  },
  actionSheetTapAlertText() {
    this.common({
      alertText: this.data.alertText,
      itemList: this.itemList()
    });
  },
  actionSheetTapColor() {
    this.common({
      itemList: this.itemList(),
      itemColor: this.data.itemColor
    });
  }
}, __templateJs));